import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

# Importamos las clases REALES
from chaos_engine.agents.petstore import PetstoreAgent
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.resilience import CircuitBreakerProxy

# --- FIXTURES DE INTEGRACIÓN ---

@pytest.fixture
def integration_playbook(tmp_path):
    """Genera un playbook real en disco para el test."""
    playbook_content = {
        "default": {"strategy": "retry"},
        "get_inventory": {
            "503": {"strategy": "wait", "config": {"wait_seconds": 1}}
        }
    }
    d = tmp_path / "assets" / "playbooks"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "integration.json"
    f.write_text(json.dumps(playbook_content), encoding='utf-8')
    return str(f)

# --- TESTS DE INTEGRACIÓN ---

@pytest.mark.asyncio
async def test_full_stack_happy_path(integration_playbook):
    """
    INTEGRATION TEST: Verifica la pila completa:
    Agent -> CircuitBreaker -> ChaosProxy (MockMode)
    
    Objetivo: Asegurar que las dependencias se inyectan y comunican correctamente
    sin errores de tipos o de atributos.
    """
    # 1. Configuración de la Pila (STACK)
    
    # Capa 1: Chaos Proxy (En modo Mock para determinismo y velocidad)
    # Usamos failure_rate=0.0 para probar el camino feliz primero
    real_proxy = ChaosProxy(failure_rate=0.0, seed=42, mock_mode=True, verbose=True)
    
    # Capa 2: Circuit Breaker (Envolviendo al Proxy)
    real_circuit_breaker = CircuitBreakerProxy(
        wrapped_executor=real_proxy, 
        failure_threshold=5, 
        cooldown_seconds=10
    )
    
    # Capa 3: Agente (Usando el Circuit Breaker)
    # Mockeamos el constructor del LLM porque no queremos validar credenciales de Google aquí
    mock_llm_ctor = MagicMock()
    
    agent = PetstoreAgent(
        playbook_path=integration_playbook,
        tool_executor=real_circuit_breaker, # <--- ¡Inyección Real!
        llm_client_constructor=mock_llm_ctor,
        model_name="integration-test-model",
        verbose=True
    )
    
    # 2. Simulación de la Orquestación (El "Cerebro")
    # Al igual que en los unit tests, parcheamos LlmAgent y Runner para simular
    # que el modelo decide llamar a las herramientas en orden correcto.
    with patch("chaos_engine.agents.petstore.LlmAgent") as MockLlmAgent, \
         patch("chaos_engine.agents.petstore.InMemoryRunner") as MockRunner:
        
        runner_instance = MockRunner.return_value
        
        # Definimos el comportamiento: El LLM llama a las 4 herramientas secuencialmente
        async def simulate_llm_execution(*args, **kwargs):
            print("\n🤖 [SIMULADOR LLM] Ejecutando secuencia de herramientas...")
            
            # Paso 1
            print("   -> Call: get_inventory")
            await agent.get_inventory()
            
            # Paso 2
            print("   -> Call: find_pets_by_status")
            await agent.find_pets_by_status()
            
            # Paso 3
            print("   -> Call: place_order")
            await agent.place_order(123, 1)
            
            # Paso 4
            print("   -> Call: update_pet_status")
            await agent.update_pet_status(123, "sold", "sold")
            
        runner_instance.run_debug.side_effect = simulate_llm_execution
        
        # 3. Ejecución del Test
        print("\n🚀 INICIANDO TEST DE INTEGRACIÓN: Full Stack Happy Path")
        result = await agent.process_order("INT-ORDER-001", failure_rate=0.0, seed=42)
        
        # 4. Validaciones
        print(f"📊 Resultado: {result['status']}")
        
        # A) El estado final debe ser éxito
        assert result["status"] == "success"
        
        # B) Se deben haber completado los 4 pasos
        assert len(result["steps_completed"]) == 4
        assert "get_inventory" in result["steps_completed"]
        
        # C) Validación interna del Circuit Breaker
        # Como no hubo fallos, el circuito debe estar cerrado y con 0 fallos
        assert real_circuit_breaker._is_open is False
        assert real_circuit_breaker._failures == 0

@pytest.mark.asyncio
async def test_full_stack_resilience_circuit_open(integration_playbook):
    """
    INTEGRATION TEST: Verifica que el Circuit Breaker corta la conexión
    si el Proxy falla repetidamente.
    """
    # 1. Configuración: Proxy que SIEMPRE falla
    # failure_rate=1.0 asegura error en cada llamada
    failing_proxy = ChaosProxy(failure_rate=1.0, seed=42, mock_mode=True)
    
    # Circuit Breaker muy sensible (se abre al primer error)
    circuit_breaker = CircuitBreakerProxy(
        wrapped_executor=failing_proxy, 
        failure_threshold=1, 
        cooldown_seconds=60
    )
    
    agent = PetstoreAgent(
        playbook_path=integration_playbook,
        tool_executor=circuit_breaker,
        llm_client_constructor=MagicMock(),
        model_name="integration-test-model"
    )
    
    # 2. Simulación
    with patch("chaos_engine.agents.petstore.LlmAgent"), \
         patch("chaos_engine.agents.petstore.InMemoryRunner") as MockRunner:
        
        runner_instance = MockRunner.return_value
        
        async def simulate_fail_loop(*args, **kwargs):
            # Intento 1: Falla el Proxy -> Circuit Breaker cuenta 1 fallo -> SE ABRE
            await agent.get_inventory()
            
            # Intento 2: El Proxy NI SE ENTERA. El Circuit Breaker bloquea la llamada inmediatamente.
            # Esto prueba que la protección funciona.
            await agent.get_inventory()
            
        runner_instance.run_debug.side_effect = simulate_fail_loop
        
        # 3. Ejecución
        await agent.process_order("INT-FAIL-001", 0.0, 42)
        
        # 4. Validaciones
        # El circuito debe estar abierto
        assert circuit_breaker._is_open is True
        assert circuit_breaker._failures >= 1