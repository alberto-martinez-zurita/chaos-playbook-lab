"""
Unit tests for chaos injection framework.

Location: tests/unit/test_chaos_injection.py
Based on: ADR-005 & ADR-006
Purpose: Validate ChaosConfig class and injection logic
"""

import pytest
import asyncio
from datetime import datetime

from chaos_playbook_engine.config.chaos_config import ChaosConfig, create_chaos_config
from chaos_playbook_engine.tools.chaos_injection_helper import (
    inject_chaos_failure,
    is_retryable_error,
    get_suggested_backoff,
    is_chaos_injected
)


# ═════════════════════════════════════════════════════════════════
# TESTS: ChaosConfig Class
# ═════════════════════════════════════════════════════════════════

class TestChaosConfigInitialization:
    """Test ChaosConfig initialization and defaults."""
    
    def test_default_initialization(self):
        """Test ChaosConfig with defaults (disabled)."""
        config = ChaosConfig()
        
        assert config.enabled is False
        assert config.failure_rate == 0.0
        assert config.failure_type == "timeout"
        assert config.max_delay_seconds == 2
        assert config.seed is None
    
    def test_enabled_initialization(self):
        """Test ChaosConfig with chaos enabled."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            failure_type="service_unavailable",
            max_delay_seconds=3,
            seed=42
        )
        
        assert config.enabled is True
        assert config.failure_rate == 0.5
        assert config.failure_type == "service_unavailable"
        assert config.max_delay_seconds == 3
        assert config.seed == 42
    
    def test_repr(self):
        """Test string representation."""
        config = ChaosConfig(enabled=True, failure_rate=1.0, seed=42)
        
        repr_str = repr(config)
        assert "enabled=True" in repr_str
        assert "failure_rate=1.0" in repr_str
        assert "seed=42" in repr_str


class TestChaosConfigDeterminism:
    """Test deterministic behavior with seed."""
    
    def test_seed_reproducibility(self):
        """Test that same seed produces same results."""
        config1 = ChaosConfig(enabled=True, failure_rate=0.5, seed=42)
        config2 = ChaosConfig(enabled=True, failure_rate=0.5, seed=42)
        
        results1 = [config1.should_inject_failure() for _ in range(10)]
        results2 = [config2.should_inject_failure() for _ in range(10)]
        
        assert results1 == results2, "Same seed should produce same results"
    
    def test_different_seeds_produce_different_results(self):
        """Test that different seeds can produce different results."""
        config1 = ChaosConfig(enabled=True, failure_rate=0.5, seed=42)
        config2 = ChaosConfig(enabled=True, failure_rate=0.5, seed=123)
        
        results1 = [config1.should_inject_failure() for _ in range(20)]
        results2 = [config2.should_inject_failure() for _ in range(20)]
        
        # At least some results should differ (very unlikely to be identical)
        assert results1 != results2, "Different seeds should produce different results"


class TestChaosConfigShouldInjectFailure:
    """Test should_inject_failure() logic."""
    
    def test_disabled_returns_false(self):
        """Test that disabled chaos always returns False."""
        config = ChaosConfig(enabled=False, failure_rate=1.0)
        
        for _ in range(10):
            assert config.should_inject_failure() is False
    
    def test_enabled_with_100_percent_rate(self):
        """Test 100% failure rate always returns True."""
        config = ChaosConfig(enabled=True, failure_rate=1.0, seed=42)
        
        for _ in range(10):
            assert config.should_inject_failure() is True
    
    def test_enabled_with_zero_percent_rate(self):
        """Test 0% failure rate always returns False."""
        config = ChaosConfig(enabled=True, failure_rate=0.0, seed=42)
        
        for _ in range(10):
            assert config.should_inject_failure() is False
    
    def test_enabled_with_50_percent_rate(self):
        """Test 50% failure rate produces mixed results."""
        config = ChaosConfig(enabled=True, failure_rate=0.5, seed=42)
        
        results = [config.should_inject_failure() for _ in range(100)]
        
        num_failures = sum(results)
        # Should be approximately 50 (allow 30-70 range)
        assert 30 < num_failures < 70, f"Expected ~50 failures, got {num_failures}"


class TestChaosConfigDelay:
    """Test get_delay_seconds() logic."""
    
    @pytest.mark.asyncio
    async def test_delay_for_timeout_type(self):
        """Test delay generation for timeout failure type."""
        config = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42
        )
        
        delay = config.get_delay_seconds()
        
        assert 1.0 <= delay <= 5.0, f"Delay should be 1-5 seconds, got {delay}"
    
    def test_no_delay_for_non_timeout_type(self):
        """Test no delay for non-timeout failure types."""
        config = ChaosConfig(
            enabled=True,
            failure_type="service_unavailable",
            max_delay_seconds=2,
            seed=42
        )
        
        delay = config.get_delay_seconds()
        
        assert delay == 0.0, "Non-timeout should have 0 delay"


# ═════════════════════════════════════════════════════════════════
# TESTS: Chaos Injection Helper Functions
# ═════════════════════════════════════════════════════════════════

class TestInjectChaosFailure:
    """Test inject_chaos_failure() function."""
    
    @pytest.mark.asyncio
    async def test_timeout_error_response(self):
        """Test timeout error response structure."""
        config = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=1,
            seed=42
        )
        
        result = await inject_chaos_failure("inventory", "check_stock", config)
        
        assert result["status"] == "error"
        assert result["error_code"] == "TIMEOUT"
        assert result["retryable"] is True
        assert result["message"]  # Non-empty message
        assert result["metadata"]["api"] == "inventory"
        assert result["metadata"]["endpoint"] == "check_stock"
        assert result["metadata"]["chaos_injected"] is True
        assert "suggested_backoff_seconds" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_service_unavailable_error_response(self):
        """Test 503 service unavailable response."""
        config = ChaosConfig(
            enabled=True,
            failure_type="service_unavailable",
            seed=42
        )
        
        result = await inject_chaos_failure("payments", "capture", config)
        
        assert result["status"] == "error"
        assert result["error_code"] == "SERVICE_UNAVAILABLE"
        assert result["retryable"] is True
        assert "503" in result["message"]
    
    @pytest.mark.asyncio
    async def test_invalid_request_error_response(self):
        """Test 400 invalid request response."""
        config = ChaosConfig(
            enabled=True,
            failure_type="invalid_request",
            seed=42
        )
        
        result = await inject_chaos_failure("inventory", "check_stock", config)
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_REQUEST"
        assert result["retryable"] is False  # Non-retryable
    
    @pytest.mark.asyncio
    async def test_cascade_error_response(self):
        """Test cascade failure response."""
        config = ChaosConfig(
            enabled=True,
            failure_type="cascade",
            seed=42
        )
        
        result = await inject_chaos_failure("erp", "create_order", config)
        
        assert result["status"] == "error"
        assert result["error_code"] == "CASCADE_FAILURE"
        assert result["retryable"] is False  # Cascade not retryable
    
    @pytest.mark.asyncio
    async def test_partial_error_response(self):
        """Test partial failure response."""
        config = ChaosConfig(
            enabled=True,
            failure_type="partial",
            seed=42
        )
        
        result = await inject_chaos_failure("shipping", "create_shipment", config)
        
        assert result["status"] == "error"
        assert result["error_code"] == "PARTIAL_FAILURE"
        assert result["retryable"] is True
        assert "partial" in result["message"].lower()
    
    @pytest.mark.asyncio
    async def test_disabled_chaos_raises_error(self):
        """Test that disabled chaos raises ValueError."""
        config = ChaosConfig(enabled=False)
        
        with pytest.raises(ValueError, match="must have enabled=True"):
            await inject_chaos_failure("inventory", "check_stock", config)


class TestChaosHelperFunctions:
    """Test helper functions for error analysis."""
    
    def test_is_retryable_error_true(self):
        """Test is_retryable_error with retryable=True."""
        error = {
            "status": "error",
            "error_code": "TIMEOUT",
            "retryable": True
        }
        
        assert is_retryable_error(error) is True
    
    def test_is_retryable_error_false(self):
        """Test is_retryable_error with retryable=False."""
        error = {
            "status": "error",
            "error_code": "INVALID_REQUEST",
            "retryable": False
        }
        
        assert is_retryable_error(error) is False
    
    def test_is_retryable_error_missing_field(self):
        """Test is_retryable_error with missing retryable field."""
        error = {"status": "error"}
        
        assert is_retryable_error(error) is False
    
    def test_get_suggested_backoff(self):
        """Test get_suggested_backoff extraction."""
        error = {
            "metadata": {
                "suggested_backoff_seconds": 8
            }
        }
        
        assert get_suggested_backoff(error) == 8
    
    def test_get_suggested_backoff_default(self):
        """Test get_suggested_backoff with missing field."""
        error = {"metadata": {}}
        
        assert get_suggested_backoff(error) == 2  # Default
    
    def test_is_chaos_injected_true(self):
        """Test is_chaos_injected with chaos_injected=True."""
        error = {
            "metadata": {
                "chaos_injected": True
            }
        }
        
        assert is_chaos_injected(error) is True
    
    def test_is_chaos_injected_false(self):
        """Test is_chaos_injected with chaos_injected=False."""
        error = {
            "metadata": {
                "chaos_injected": False
            }
        }
        
        assert is_chaos_injected(error) is False


class TestFactoryFunction:
    """Test create_chaos_config factory function."""
    
    def test_factory_creates_valid_config(self):
        """Test factory creates ChaosConfig correctly."""
        config = create_chaos_config("timeout", failure_rate=0.5, max_delay=3, seed=42)
        
        assert config.enabled is True
        assert config.failure_type == "timeout"
        assert config.failure_rate == 0.5
        assert config.max_delay_seconds == 3
        assert config.seed == 42
    
    def test_factory_invalid_failure_rate(self):
        """Test factory rejects invalid failure_rate."""
        with pytest.raises(ValueError, match="failure_rate must be 0.0-1.0"):
            create_chaos_config("timeout", failure_rate=1.5)
    
    def test_factory_invalid_max_delay(self):
        """Test factory rejects invalid max_delay."""
        with pytest.raises(ValueError, match="max_delay must be > 0"):
            create_chaos_config("timeout", max_delay=0)
    
    def test_factory_invalid_failure_type(self):
        """Test factory rejects invalid failure_type."""
        with pytest.raises(ValueError, match="Invalid failure_type"):
            create_chaos_config("invalid_type")


# ═════════════════════════════════════════════════════════════════
# INTEGRATION-LIKE TESTS
# ═════════════════════════════════════════════════════════════════

class TestChaosIntegration:
    """Integration tests combining ChaosConfig and injection."""
    
    @pytest.mark.asyncio
    async def test_deterministic_scenario_sequence(self):
        """Test deterministic sequence with seed."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=1.0,
            failure_type="service_unavailable",
            seed=42
        )
        
        # First call
        result1 = await inject_chaos_failure("api1", "endpoint1", config)
        assert result1["error_code"] == "SERVICE_UNAVAILABLE"
        
        # Second call (should be same error type due to seed)
        result2 = await inject_chaos_failure("api2", "endpoint2", config)
        assert result2["error_code"] == "SERVICE_UNAVAILABLE"
    
    @pytest.mark.asyncio
    async def test_mixed_scenario(self):
        """Test mixed success/failure scenario."""
        config_fail = ChaosConfig(
            enabled=True,
            failure_rate=1.0,
            failure_type="timeout",
            seed=42
        )
        config_success = ChaosConfig(enabled=False)
        
        # First request fails
        result1 = config_fail.should_inject_failure()
        assert result1 is True
        
        # Second request succeeds
        result2 = config_success.should_inject_failure()
        assert result2 is False


# ═════════════════════════════════════════════════════════════════
# FIXTURES FOR PYTEST
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
def chaos_timeout_config():
    """Fixture: Always timeout."""
    return ChaosConfig(
        enabled=True,
        failure_rate=1.0,
        failure_type="timeout",
        max_delay_seconds=1,
        seed=42
    )


@pytest.fixture
def chaos_503_config():
    """Fixture: Always 503."""
    return ChaosConfig(
        enabled=True,
        failure_rate=1.0,
        failure_type="service_unavailable",
        seed=123
    )


@pytest.fixture
def chaos_400_config():
    """Fixture: Always 400."""
    return ChaosConfig(
        enabled=True,
        failure_rate=1.0,
        failure_type="invalid_request",
        seed=456
    )


@pytest.fixture
def chaos_50pct_config():
    """Fixture: 50% random failures."""
    return ChaosConfig(
        enabled=True,
        failure_rate=0.5,
        failure_type="service_unavailable",
        seed=789
    )
