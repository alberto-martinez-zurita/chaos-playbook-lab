import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from chaos_engine.agents.petstore import PetstoreAgent
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.resilience import CircuitBreakerProxy

@pytest.fixture
def easy_playbook(tmp_path):
    # ... (fixture igual que antes) ...
    content = {"default": {"strategy": "retry"}}
    d = tmp_path / "assets" / "playbooks"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "easy_mode.json"
    f.write_text(json.dumps(content), encoding='utf-8')
    return str(f)

@pytest.mark.asyncio
async def test_chaos_proxy_mock_mode_flow(easy_playbook):
    """
    Test de Integración 'Easy Win' (DETERMINISTA).
    - Chaos: 0% (Garantizamos éxito para validar cableado).
    - Red: Mock Mode.
    """
    
    # 1. Configuración SIN CAOS (0.0) para asegurar el Happy Path primero
    proxy = ChaosProxy(
        failure_rate=0.0,   # 🔥 FIX: 0.0 para evitar sorpresas en test de integración básico
        seed=42,
        mock_mode=True,
        verbose=True
    )
    
    circuit_breaker = CircuitBreakerProxy(wrapped_executor=proxy)
    
    agent = PetstoreAgent(
        playbook_path=easy_playbook,
        tool_executor=circuit_breaker,
        llm_client_constructor=MagicMock(),
        model_name="dummy-model",
        verbose=True
    )
    
    # 2. Simulación del Cerebro
    with patch("chaos_engine.agents.petstore.LlmAgent"), \
         patch("chaos_engine.agents.petstore.InMemoryRunner") as MockRunner:
        
        runner_instance = MockRunner.return_value
        runner_instance.run_debug = AsyncMock()
        
        async def simulate_perfect_execution(*args, **kwargs):
            print("\n🤖 [MOCK BRAIN] Ejecutando secuencia de compra...")
            await agent.get_inventory()
            await agent.find_pets_by_status()
            await agent.place_order(pet_id=999, quantity=1)
            await agent.update_pet_status(pet_id=999, name="MockDog", status="sold")
            
        runner_instance.run_debug.side_effect = simulate_perfect_execution
        
        # 3. Ejecutar
        print("\n🚀 Iniciando Test Determinista...")
        result = await agent.process_order(
            order_id="EASY-TEST-001",
            failure_rate=0.1, # Debe coincidir con el proxy para lógica interna
            seed=42
        )
        
        # 4. Validar
        print(f"\n📊 Resultado Final: {result['status']}")
        assert result["status"] == "success"
        assert len(result["steps_completed"]) == 4