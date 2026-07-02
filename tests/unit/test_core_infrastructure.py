import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
from chaos_engine.core.config import ConfigLoader
from chaos_engine.core.resilience import CircuitBreakerProxy

# --- TEST CONFIGURATION ---

@patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key-for-unit-test"})
def test_config_loader_structure(tmp_path):
    """Verify the loader reads YAML from the correct path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    yaml_content = (
        "environment: dev\n"
        "agent:\n"
        "  model: test-model\n"
        "session_service:\n"
        "  db_url: 'sqlite:///:memory:'"
    )

    (config_dir / "dev.yaml").write_text(yaml_content, encoding='utf-8')

    loader = ConfigLoader(config_dir=config_dir)
    config = loader.load("dev")

    assert config["environment"] == "dev"
    assert config["agent"]["model"] == "test-model"
    assert config["session_service"]["db_url"] == "sqlite:///:memory:"

# --- TEST CIRCUIT BREAKER (Pilar IV) ---

@pytest.mark.asyncio
async def test_circuit_breaker_closes_on_success(mock_executor):
    """El circuito debe permanecer cerrado (pasando tráfico) si hay éxitos."""
    cb = CircuitBreakerProxy(wrapped_executor=mock_executor, failure_threshold=3)
    
    # Ejecutar petición exitosa
    result = await cb.send_request("GET", "/test")
    
    assert result["status"] == "success"
    assert cb._failures == 0
    assert cb._is_open is False

@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures(mock_failing_executor):
    """El circuito debe abrirse tras superar el umbral de fallos."""
    cb = CircuitBreakerProxy(wrapped_executor=mock_failing_executor, failure_threshold=2, cooldown_seconds=1)
    
    # Fallo 1
    await cb.send_request("GET", "/test")
    assert cb._failures == 1
    assert cb._is_open is False
    
    # Fallo 2 (Umbral alcanzado)
    await cb.send_request("GET", "/test")
    assert cb._failures == 2
    assert cb._is_open is True # 🔥 OPEN

    # Intento 3: Debe ser bloqueado por el Circuit Breaker (no llega al executor)
    result = await cb.send_request("GET", "/test")

    # Verificación: el CB devuelve error 503 sin llamar al executor
    assert result["status"] == "error"
    assert result["code"] == 503
    assert "Circuit Breaker Open" in result["message"]

@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery(mock_executor):
    """El circuito debe intentar recuperarse tras el cooldown."""
    # Setup: Circuito ya abierto
    cb = CircuitBreakerProxy(wrapped_executor=mock_executor, failure_threshold=1, cooldown_seconds=0.1)
    cb._is_open = True
    cb._opened_timestamp = time.time() - 0.2 # Pasamos el cooldown simulado
    
    # Ejecución (Estado Half-Open -> Success -> Closed)
    result = await cb.send_request("GET", "/test")
    
    assert result["status"] == "success"
    assert cb._is_open is False # Se cerró de nuevo
    assert cb._failures == 0