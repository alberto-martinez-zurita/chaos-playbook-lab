from typing import Dict, Any, Optional
from chaos_engine.agents.petstore import ToolExecutor

# Mock del executor (Proxy)
class MockSuccessExecutor:
    """Simula un ChaosProxy que SIEMPRE devuelve éxito."""
    async def send_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_body: Optional[Dict] = None) -> Dict[str, Any]:
        # Siempre éxito con datos mínimos para que el agente avance
        return {"status": "success", "code": 200, "data": {"id": 123, "name": "MockPet"}}

# Mock del LLM (Solo constructor)
class MockGeminiConstructor:
    """Simula la instanciación de la clase Gemini."""
    def __init__(self, *args, **kwargs):
        pass # No hace falta nada aquí
    # El agente ADK solo necesita que se pueda instanciar.