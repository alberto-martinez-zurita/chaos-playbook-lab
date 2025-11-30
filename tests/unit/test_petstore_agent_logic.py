import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from chaos_engine.agents.petstore import PetstoreAgent

# --- TESTS DE NEGOCIO (TOOLS) ---

@pytest.mark.asyncio
async def test_get_inventory_success(mock_executor, mock_llm_constructor, temp_playbook_file):
    agent = PetstoreAgent(temp_playbook_file, mock_executor, mock_llm_constructor, "model")
    
    await agent.get_inventory()
    
    assert "get_inventory" in agent.successful_steps
    mock_executor.send_request.assert_called_with("GET", "/store/inventory")

@pytest.mark.asyncio
async def test_wait_seconds_jitter(mock_executor, mock_llm_constructor, temp_playbook_file):
    """Verificar que wait_seconds usa el cálculo de jitter del executor."""
    agent = PetstoreAgent(temp_playbook_file, mock_executor, mock_llm_constructor, "model")
    
    # Mockear el cálculo de jitter en el executor
    mock_executor.calculate_jittered_backoff = lambda s: s + 0.1
    
    # 🔥 FIX 2: Eliminamos el bloque 'pytest.raises' vacío que causaba el fallo.
    # Ahora usamos patch correctamente para simular el sleep.
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await agent.wait_seconds(2.0)
        
        # Debe haber llamado a sleep con 2.1 (según nuestra lambda mock)
        mock_sleep.assert_called_with(2.1)
        assert res["status"] == "success"

# --- TEST DE ORQUESTACIÓN (PROCESS ORDER) ---

@pytest.mark.asyncio
async def test_process_order_success_flow(mock_executor, mock_llm_constructor, temp_playbook_file):
    """
    Verifica que process_order detecta éxito si se completan todos los pasos.
    """
    agent = PetstoreAgent(temp_playbook_file, mock_executor, mock_llm_constructor, "model", verbose=True)
    
    # 🔥 FIX: Mockeamos LlmAgent para evitar errores de validación de Pydantic.
    # No necesitamos que LlmAgent sea real, solo que el código pase por ahí.
    with patch("chaos_engine.agents.petstore.LlmAgent") as MockLlmAgent, \
         patch("chaos_engine.agents.petstore.InMemoryRunner") as MockRunner:
        
        # Configurar el Runner Mock
        runner_instance = MockRunner.return_value
        runner_instance.run_debug = AsyncMock()
        
        # Simulamos que el LLM ejecuta las tools exitosamente (side_effect)
        async def side_effect_run_debug(*args, **kwargs):
            await agent.get_inventory()
            await agent.find_pets_by_status()
            await agent.place_order(1, 1)
            await agent.update_pet_status(1, "sold", "sold")
        
        runner_instance.run_debug.side_effect = side_effect_run_debug
        
        # Ejecutar
        result = await agent.process_order("ORD-1", 0.0, 42)
        
        # Verificaciones
        assert result["status"] == "success"
        assert len(result["steps_completed"]) == 4
        assert result["failed_at"] == "unknown"
        # Verificar que se intentó crear el agente (aunque fuera un mock)
        MockLlmAgent.assert_called_once()

@pytest.mark.asyncio
async def test_process_order_failure_flow(mock_executor, mock_llm_constructor, temp_playbook_file):
    """Verifica que detecta fallo si faltan pasos."""
    agent = PetstoreAgent(temp_playbook_file, mock_executor, mock_llm_constructor, "model")
    
    # 🔥 FIX: Mockeamos LlmAgent también aquí
    with patch("chaos_engine.agents.petstore.LlmAgent") as MockLlmAgent, \
         patch("chaos_engine.agents.petstore.InMemoryRunner") as MockRunner:
        
        runner_instance = MockRunner.return_value
        
        # Simulamos ejecución parcial
        async def side_effect_partial(*args, **kwargs):
            await agent.get_inventory()
            
        runner_instance.run_debug.side_effect = side_effect_partial
        
        result = await agent.process_order("ORD-FAIL", 0.0, 42)
        
        assert result["status"] == "failure"
        assert result["failed_at"] == "incomplete_workflow"
        assert len(result["steps_completed"]) == 1