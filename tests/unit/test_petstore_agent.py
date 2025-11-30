import pytest
from pathlib import Path
from chaos_engine.agents.petstore import PetstoreAgent
from mocks import MockSuccessExecutor, MockGeminiConstructor # Asumiendo la ubicación de mocks

# Ruta al playbook (usamos el weak, pero realmente no importa en este test)
PLAYBOOK_PATH = str(Path.cwd() / "assets/playbooks/weak.json")

# ✅ 1. Testear Inicialización y Contrato
def test_agent_initialization():
    executor = MockSuccessExecutor()
    
    # ✅ PILAR III: Inyectamos el Mock en lugar del ChaosProxy real
    agent = PetstoreAgent(
        playbook_path=PLAYBOOK_PATH,
        tool_executor=executor,
        llm_client_constructor=MockGeminiConstructor,
        model_name="mock-model"
    )
    
    assert isinstance(agent.successful_steps, set)
    assert agent.executor is executor

# ✅ 2. Testear Lógica de Pasos (Integración de tools)
@pytest.mark.asyncio
async def test_agent_executes_tools_and_counts_success():
    executor = MockSuccessExecutor()
    agent = PetstoreAgent(
        playbook_path=PLAYBOOK_PATH,
        tool_executor=executor,
        llm_client_constructor=MockGeminiConstructor,
        model_name="mock-model"
    )
    
    # Ejecutar las herramientas de forma secuencial
    await agent.get_inventory()
    await agent.find_pets_by_status()
    await agent.place_order(pet_id=1, quantity=1)
    
    # Comprobar que el estado interno se actualizó correctamente
    assert "get_inventory" in agent.successful_steps
    assert len(agent.successful_steps) == 3
    
    # Comprobar que el agente pasa la lista de herramientas correcta
    tools = agent.get_tool_list()
    assert len(tools) == 7 # Contando las 4 de negocio + lookup + wait + failure