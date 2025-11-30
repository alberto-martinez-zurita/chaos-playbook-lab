"""
Evaluation Runner - Validates agent against defined test cases.
Updated with Observability (Logging) and Phase 6 Dependency Injection.
"""
import json
import time
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# ✅ Nuevas importaciones para la Inyección de Dependencias
from chaos_engine.agents.petstore import PetstoreAgent
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.resilience import CircuitBreakerProxy
from chaos_engine.core.config import load_config, get_model_name
from google.adk.models.google_llm import Gemini

@dataclass
class TestResult:
    case_id: str
    passed: bool
    reason: str
    duration: float
    metrics: Dict[str, Any]
    
    def to_dict(self):
        return asdict(self)

class EvaluationRunner:
    def __init__(self, agent_playbook: str):
        self.logger = logging.getLogger("evaluator")
        self.playbook_path = agent_playbook
        
        # 1. Cargar Configuración General
        self.config = load_config()
        self.model_name = get_model_name(self.config)
        
        # 🔥 FIX: Leer mock_mode de la configuración global
        self.mock_mode = self.config.get("mock_mode", False)
        
        # 2. Inicializar dependencias por defecto
        # 🔥 FIX: Pasar mock_mode aquí
        self.current_proxy = ChaosProxy(
            failure_rate=0.0, 
            seed=42, 
            verbose=True, 
            mock_mode=self.mock_mode
        )
        self.circuit_breaker = CircuitBreakerProxy(wrapped_executor=self.current_proxy)

        # 3. Inyectar dependencias al Agente
        self.agent = PetstoreAgent(
            playbook_path=agent_playbook,
            tool_executor=self.circuit_breaker,
            llm_client_constructor=Gemini,
            model_name=self.model_name,
            verbose=True
        )

    async def run_suite(self, suite_path: str) -> List[TestResult]:
        """Ejecuta una suite completa de tests definida en JSON."""
        
        with open(suite_path, 'r', encoding='utf-8') as f:
            suite = json.load(f)
            
        self.logger.info(f"🧪 STARTING SUITE: {suite['name']}")
        self.logger.info(f"⚙️  MODE: {'MOCK (Offline)' if self.mock_mode else 'REAL API'}")
        
        results = []
        for case in suite['test_cases']:
            self.logger.info(f"\n🔹 Running Case: {case['id']} ({case['description']})")
            result = await self._run_single_case(case)
            results.append(result)
            
            icon = "✅" if result.passed else "❌"
            self.logger.info(f"   Result: {icon} {result.reason} ({result.duration:.2f}s)")
            
        return results

    async def _run_single_case(self, case: Dict) -> TestResult:
        start_time = time.time()
        chaos_config = case['chaos_config']
        
        # 🔥 ACTUALIZACIÓN DINÁMICA DE DEPENDENCIAS
        # Aseguramos que el proxy del test también respete el mock_mode
        test_proxy = ChaosProxy(
            failure_rate=chaos_config['rate'],
            seed=chaos_config['seed'],
            verbose=True,
            mock_mode=self.mock_mode # <--- ¡Importante!
        )
        
        test_executor = CircuitBreakerProxy(wrapped_executor=test_proxy)
        
        # Intercambiamos el executor del agente "en caliente"
        self.agent.executor = test_executor
        
        # Ejecución
        try:
            output = await self.agent.process_order(
                order_id=case['input'],
                failure_rate=chaos_config['rate'],
                seed=chaos_config['seed']
            )
        except Exception as e:
            return TestResult(
                case['id'], 
                False, 
                f"Crash during execution: {str(e)}", 
                time.time() - start_time, 
                {"error": str(e)}
            )
        
        duration = time.time() - start_time
        expected = case['expected']
        
        # --- Lógica de Aserciones ---
        if output['status'] != expected['status']:
            return TestResult(case['id'], False, f"Status mismatch: Got {output['status']}, expected {expected['status']}", duration, output)
            
        if 'max_latency_ms' in expected and output['duration_ms'] > expected['max_latency_ms']:
             return TestResult(case['id'], False, f"Latency violation: {output['duration_ms']:.0f}ms > {expected['max_latency_ms']}ms", duration, output)

        steps_set = set(output.get('steps_completed', []))
        if 'must_call' in expected:
            missing = [tool for tool in expected['must_call'] if tool not in steps_set and tool != "lookup_playbook"]
            if missing:
                return TestResult(case['id'], False, f"Missing required steps: {missing}", duration, output)
        
        if 'forbidden_outcome' in expected and output['status'] == expected['forbidden_outcome']:
             return TestResult(case['id'], False, f"Forbidden outcome occurred: {output['status']}", duration, output)

        return TestResult(case['id'], True, "Passed all assertions", duration, output)