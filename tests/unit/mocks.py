from __future__ import annotations

from typing import Any, Dict, Optional

from chaos_engine.core.protocols import Executor

# Mock del executor (Proxy)
class MockSuccessExecutor:
    """Simula un ChaosProxy que SIEMPRE devuelve éxito."""
    async def send_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_body: Optional[Dict] = None) -> Dict[str, Any]:
        return {"status": "success", "code": 200, "data": {"id": 123, "name": "MockPet"}}

    def calculate_jittered_backoff(self, seconds: float) -> float:
        return seconds

# Mock del LLM (Solo constructor)
class MockGeminiConstructor:
    """Simula la instanciación de la clase Gemini."""
    def __init__(self, *args, **kwargs):
        pass # No hace falta nada aquí
    # El agente ADK solo necesita que se pueda instanciar.