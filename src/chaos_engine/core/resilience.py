"""
Resilience Utilities - Circuit Breaker Implementation (Pilar IV).
"""
import time
import logging
from typing import Dict, Any, Optional, Protocol, runtime_checkable

# Reutilizar el protocolo de ejecución de herramientas
@runtime_checkable
class Executor(Protocol):
    async def send_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_body: Optional[Dict] = None) -> Dict[str, Any]: ...
    # Añadimos el método al protocolo para que mypy sea feliz (opcional pero buena práctica)
    def calculate_jittered_backoff(self, seconds: float) -> float: ...

class CircuitBreakerProxy:
    """
    Implementa el patrón Circuit Breaker para proteger el servicio de destino.
    Si el número de fallos consecutivos supera el umbral, el circuito se abre.
    """
    
    def __init__(self, wrapped_executor: Executor, failure_threshold: int = 5, cooldown_seconds: int = 60):
        self._executor = wrapped_executor
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        
        # Estado del circuito
        self._failures = 0
        self._is_open = False
        self._opened_timestamp = 0
        self.logger = logging.getLogger("CircuitBreaker")

    # 🔥 FIX: Implementar el método que faltaba y delegarlo al executor interno
    def calculate_jittered_backoff(self, seconds: float) -> float:
        """Delega el cálculo de jitter al componente interno (ChaosProxy)."""
        if hasattr(self._executor, "calculate_jittered_backoff"):
            return self._executor.calculate_jittered_backoff(seconds)
        # Fallback si el executor interno no tiene el método
        return seconds

    async def send_request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_body: Optional[Dict] = None) -> Dict[str, Any]:
        
        # 1. ESTADO ABIERTO (Protección)
        if self._is_open:
            if time.time() < self._opened_timestamp + self._cooldown_seconds:
                self.logger.warning(f"🚨 CIRCUIT OPEN: Request to {endpoint} blocked (Cooldown active).")
                # Devolver un error de servicio inalcanzable inmediatamente (Pilar IV: MTTR bajo)
                return {"status": "error", "code": 503, "message": "Circuit Breaker Open: Service is down."}
            else:
                # Transición a estado de "Semi-abierto" (permitir 1 prueba)
                self._is_open = False
                self.logger.info("🔧 CIRCUIT HALF-OPEN: Allowing one test request.")
        
        # 2. Ejecución de la solicitud
        response = await self._executor.send_request(method, endpoint, params, json_body)
        
        # 3. MANEJO DEL ESTADO
        if response.get("status") == "error":
            self._handle_failure()
        else:
            self._handle_success()

        return response

    def _handle_failure(self):
        self._failures += 1
        self.logger.debug(f"Failure count: {self._failures}/{self._failure_threshold}")
        if self._failures >= self._failure_threshold:
            self._is_open = True
            self._opened_timestamp = time.time()
            self.logger.critical(f"🛑 CIRCUIT OPENED: {self._failure_threshold} consecutive failures. Cooldown for {self._cooldown_seconds}s.")

    def _handle_success(self):
        if self._failures > 0:
            self.logger.info("✅ CIRCUIT RESET: Successful request.")
            self._failures = 0
            self._is_open = False