"""
Evaluation Runner - Validates agent against defined test cases.
Updated with Observability (Logging).
"""
import json
import time
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

from chaos_engine.agents.petstore import PetstoreAgent
# No importamos setup_logger aquí, asumimos que el CLI lo configura

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
        # verbose=True para que el agente escriba sus logs internos
        self.agent = PetstoreAgent(playbook_path=agent_playbook, verbose=True)
        self.logger = logging.getLogger("evaluator")

    async def run_suite(self, suite_path: str) -> List[TestResult]:
        """Ejecuta una suite completa de tests definida en JSON."""
        
        with open(suite_path, 'r', encoding='utf-8') as f:
            suite = json.load(f)
            
        self.logger.info(f"🧪 STARTING SUITE: {suite['name']}")
        self.logger.info(f"📝 Description: {suite['description']}")
        
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
        chaos = case['chaos_config']
        
        # Ejecución (Los logs internos del agente irán al mismo archivo gracias al Root Logger)
        output = await self.agent.process_order(
            order_id=case['input'],
            failure_rate=chaos['rate'],
            seed=chaos['seed']
        )
        
        duration = time.time() - start_time
        expected = case['expected']
        
        # Evaluaciones
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