import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, Optional

from chaos_engine.agents.petstore import PetstoreAgent

# --- 1. UTILERÍA: Executor Programable (Simulador de Red Determinista) ---

class ProgrammableExecutor:
    """
    Simula una API que falla X veces y luego funciona.
    Permite probar la resiliencia de forma determinista.
    """
    def __init__(self, failure_sequence: list):
        # Lista de respuestas a devolver en orden. 
        # Si se acaba la lista, devuelve éxito por defecto.
        self.response_queue = failure_sequence
        self.call_count = 0

    async def send_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_body: Optional[Dict] = None) -> Dict[str, Any]:
        self.call_count += 1
        
        # Si tenemos una respuesta programada para este endpoint, la usamos
        if self.response_queue:
            next_response = self.response_queue.pop(0)
            print(f"   [RED SIMULADA] Intento {self.call_count}: {next_response['status']}")
            return next_response
            
        # Por defecto éxito
        return {"status": "success", "code": 200, "data": {"mock": "data"}}

    # Método necesario para el contrato del Agente (Backoff)
    def calculate_jittered_backoff(self, seconds: float) -> float:
        return seconds  # Sin jitter para el test

# --- 2. FIXTURE DE PLAYBOOK INTELIGENTE ---

@pytest.fixture
def recovery_playbook(tmp_path):
    """Crea un playbook que sabe cómo arreglar un error 503."""
    playbook_content = {
        "default": {"strategy": "fail"},
        "get_inventory": {
            "503": {
                "strategy": "wait", 
                "reasoning": "Servicio ocupado, esperar funciona.",
                "config": {"wait_seconds": 1} # El agente leerá esto
            }
        }
    }
    d = tmp_path / "assets" / "playbooks"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "recovery.json"
    f.write_text(json.dumps(playbook_content), encoding='utf-8')
    return str(f)

# --- 3. TEST DE RECUPERACIÓN (LA JOYA DE LA CORONA) ---

@pytest.mark.asyncio
async def test_agent_recovers_from_503_using_playbook(recovery_playbook):
    """
    VALIDA LA HIPÓTESIS DEL PROYECTO:
    El agente encuentra un error, lee el playbook, espera y se recupera.
    """
    # ESCENARIO:
    # 1. get_inventory -> Falla con 503 (Service Unavailable)
    # 2. Agente -> Lee Playbook -> Dice "Wait 1s"
    # 3. Agente -> Ejecuta wait_seconds(1)
    # 4. Agente -> Reintenta get_inventory -> Éxito 200
    
    # Configurar la secuencia programada
    failure_503 = {"status": "error", "code": 503, "message": "Service Unavailable"}
    success_200 = {"status": "success", "code": 200, "data": {"available": 50}}
    
    # La cola solo afecta a las primeras llamadas. 
    # El resto de tools (find_pets, etc.) recibirán el éxito por defecto del Executor.
    executor = ProgrammableExecutor(failure_sequence=[failure_503, success_200])
    
    # Inicializar Agente
    agent = PetstoreAgent(
        playbook_path=recovery_playbook,
        tool_executor=executor,
        llm_client_constructor=MagicMock(),
        model_name="recovery-test-model",
        verbose=True
    )

    # Simular la ejecución del LLM
    with patch("chaos_engine.agents.petstore.LlmAgent"), \
         patch("chaos_engine.agents.petstore.InMemoryRunner") as MockRunner:
        
        runner_instance = MockRunner.return_value
        
        # Simular el comportamiento INTELIGENTE del LLM
        async def simulate_smart_llm(*args, **kwargs):
            print("\n🤖 [LLM] Iniciando intento de inventario...")
            
            # 1. Primer intento (Fallará programadamente)
            res1 = await agent.get_inventory()
            
            if res1["status"] == "error":
                print("   ⚠️ [LLM] Error detectado. Consultando Playbook...")
                # 2. Consultar Playbook
                strategy = await agent.lookup_playbook("get_inventory", "503")
                
                if strategy["found"] and strategy["recommendation"]["strategy"] == "wait":
                    wait_time = strategy["recommendation"]["config"]["wait_seconds"]
                    print(f"   📘 [LLM] Estrategia encontrada: Esperar {wait_time}s")
                    
                    # 3. Ejecutar Estrategia
                    await agent.wait_seconds(wait_time)
                    
                    # 4. Reintentar (Tendrás éxito programado)
                    print("   🔄 [LLM] Reintentando...")
                    await agent.get_inventory()
            
            # Completar el resto para finalizar proceso
            await agent.find_pets_by_status()
            await agent.place_order(1, 1)
            await agent.update_pet_status(1, "sold", "sold")

        runner_instance.run_debug.side_effect = simulate_smart_llm
        
        # --- EJECUCIÓN ---
        print("\n🚀 INICIANDO TEST DE RESILIENCIA: Recovery Workflow")
        result = await agent.process_order("REC-001", 0.0, 42)
        
        # --- VALIDACIONES ---
        
        # 1. El resultado final debe ser éxito (gracias a la recuperación)
        assert result["status"] == "success"
        
        # 2. El executor debe haber sido llamado más veces de lo normal (por el reintento)
        # Normal = 4 llamadas. Aquí esperamos al menos 5 (get_inventory x2)
        assert executor.call_count >= 5 
        
        # 3. Verificar que get_inventory está en los pasos exitosos
        assert "get_inventory" in result["steps_completed"]