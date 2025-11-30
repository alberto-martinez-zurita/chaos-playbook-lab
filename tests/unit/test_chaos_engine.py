import pytest
from unittest.mock import patch, MagicMock
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.chaos.config import ChaosConfig

def test_chaos_config_defaults():
    config = ChaosConfig()
    assert config.failure_rate == 0.0
    assert config.enabled is False

def test_chaos_config_seed_determinism():
    """Dos configs con la misma semilla deben producir la misma secuencia."""
    c1 = ChaosConfig(enabled=True, failure_rate=0.5, seed=42, verbose=True)
    c2 = ChaosConfig(enabled=True, failure_rate=0.5, seed=42, verbose=True)
    
    # Secuencia de 10 decisiones
    seq1 = [c1.should_inject_failure() for _ in range(10)]
    seq2 = [c2.should_inject_failure() for _ in range(10)]
    
    assert seq1 == seq2

@pytest.mark.asyncio
async def test_chaos_proxy_mock_mode():
    """El proxy en mock_mode no debe hacer llamadas de red."""
    proxy = ChaosProxy(failure_rate=0.0, seed=1, mock_mode=True)
    
    # Parcheamos httpx para asegurar que NO se llame
    with patch("httpx.AsyncClient") as mock_client:
        result = await proxy.send_request("GET", "/store/inventory")
        
        mock_client.assert_not_called()
        assert result["status"] == "success"
        assert result["data"]["available"] == 100 # Dato mockeado esperado

@pytest.mark.asyncio
async def test_chaos_proxy_injection():
    """El proxy debe inyectar error si el RNG lo decide."""
    # failure_rate=1.0 fuerza el error
    proxy = ChaosProxy(failure_rate=1.0, seed=1, mock_mode=True)
    
    result = await proxy.send_request("GET", "/store/inventory")
    
    assert result["status"] == "error"
    assert "Simulated Chaos" in result["message"]