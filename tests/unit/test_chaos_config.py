"""
Unit tests for ChaosConfig

Location: tests/unit/test_chaos_config.py

Tests cover:
- ChaosConfig creation with default values
- ChaosConfig with custom parameters
- Verbose mode functionality (NEW)
- should_inject_failure() logic
- get_delay_seconds() logic
- get_failure_response() generation
- reset_random_state() determinism
- create_chaos_config() factory function
- Equality and repr methods
"""

import pytest
import random
from chaos_playbook_engine.config.chaos_config import ChaosConfig, create_chaos_config


class TestChaosConfigCreation:
    """Test ChaosConfig initialization and defaults."""

    def test_default_config(self):
        """Test default ChaosConfig values."""
        config = ChaosConfig()

        assert config.enabled is False
        assert config.failure_rate == 0.0
        assert config.failure_type == "timeout"
        assert config.max_delay_seconds == 2
        assert config.seed is None
        assert config.verbose is False  # ✅ NEW: Test verbose default

    def test_custom_config(self):
        """Test ChaosConfig with custom values."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            failure_type="service_unavailable",
            max_delay_seconds=5,
            seed=42,
            verbose=True  # ✅ NEW: Test verbose=True
        )

        assert config.enabled is True
        assert config.failure_rate == 0.5
        assert config.failure_type == "service_unavailable"
        assert config.max_delay_seconds == 5
        assert config.seed == 42
        assert config.verbose is True  # ✅ NEW

    def test_random_instance_initialized(self):
        """Test that _random_instance is properly initialized."""
        config = ChaosConfig(seed=123)

        # Should have a random instance
        assert hasattr(config, '_random_instance')
        assert isinstance(config._random_instance, random.Random)

    def test_verbose_mode_silent_by_default(self, capsys):
        """Test that verbose mode is OFF by default (no print output)."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            seed=42
        )

        captured = capsys.readouterr()
        # Should NOT print anything when verbose=False
        assert "[CHAOS INIT]" not in captured.out

    def test_verbose_mode_prints_when_enabled(self, capsys):
        """Test that verbose mode prints debug info when enabled."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            seed=42,
            verbose=True  # ✅ Enable verbose
        )

        captured = capsys.readouterr()
        # Should print initialization info
        assert "[CHAOS INIT]" in captured.out
        assert "enabled=True" in captured.out
        assert "failure_rate=0.5" in captured.out
        assert "seed=42" in captured.out


class TestShouldInjectFailure:
    """Test should_inject_failure() logic."""

    def test_disabled_never_injects(self):
        """Test that disabled config never injects failures."""
        config = ChaosConfig(
            enabled=False,
            failure_rate=1.0,  # Even with 100% rate
            seed=42
        )

        # Should never inject when disabled
        for _ in range(10):
            assert config.should_inject_failure() is False

    def test_failure_rate_zero_never_injects(self):
        """Test that failure_rate=0.0 never injects."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.0,
            seed=42
        )

        for _ in range(10):
            assert config.should_inject_failure() is False

    def test_failure_rate_one_always_injects(self):
        """Test that failure_rate=1.0 always injects."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=1.0,
            seed=42
        )

        for _ in range(10):
            assert config.should_inject_failure() is True

    def test_failure_rate_deterministic_with_seed(self):
        """Test that same seed produces same injection pattern."""
        config1 = ChaosConfig(enabled=True, failure_rate=0.5, seed=42)
        config2 = ChaosConfig(enabled=True, failure_rate=0.5, seed=42)

        results1 = [config1.should_inject_failure() for _ in range(20)]
        results2 = [config2.should_inject_failure() for _ in range(20)]

        # Same seed should produce same pattern
        assert results1 == results2

    def test_failure_rate_approximate_distribution(self):
        """Test that failure_rate approximates expected distribution over many calls."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.3,
            seed=42
        )

        num_trials = 1000
        failures = sum(config.should_inject_failure() for _ in range(num_trials))
        failure_rate = failures / num_trials

        # Should be approximately 30% (within 5% tolerance)
        assert 0.25 <= failure_rate <= 0.35

    def test_verbose_mode_prints_injection_decision(self, capsys):
        """Test that verbose mode prints each injection decision."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            seed=42,
            verbose=True  # ✅ Enable verbose
        )

        config.should_inject_failure()

        captured = capsys.readouterr()
        # Should print decision details
        assert "[CHAOS CHECK" in captured.out
        assert "enabled=True" in captured.out
        assert "failure_rate=0.5" in captured.out
        assert "random_value=" in captured.out
        assert "inject=" in captured.out


class TestGetDelaySeconds:
    """Test get_delay_seconds() logic."""

    def test_delay_only_for_timeout(self):
        """Test that delay is only generated for timeout failures."""
        config_timeout = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=5,
            seed=42
        )

        config_other = ChaosConfig(
            enabled=True,
            failure_type="service_unavailable",
            max_delay_seconds=5,
            seed=42
        )

        # Timeout should generate delay
        delay = config_timeout.get_delay_seconds()
        assert 1.0 <= delay <= 5.0

        # Other types should return 0
        assert config_other.get_delay_seconds() == 0.0

    def test_delay_within_range(self):
        """Test that delay is within specified range."""
        config = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=3,
            seed=42
        )

        # Test multiple delays
        for _ in range(10):
            delay = config.get_delay_seconds()
            assert 1.0 <= delay <= 3.0

    def test_delay_deterministic_with_seed(self):
        """Test that same seed produces same delay pattern."""
        config1 = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=5,
            seed=123
        )

        config2 = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=5,
            seed=123
        )

        delays1 = [config1.get_delay_seconds() for _ in range(5)]
        delays2 = [config2.get_delay_seconds() for _ in range(5)]

        # Same seed should produce same delays
        assert delays1 == delays2

    def test_verbose_mode_prints_delay(self, capsys):
        """Test that verbose mode prints delay generation."""
        config = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=3,
            seed=42,
            verbose=True  # ✅ Enable verbose
        )

        config.get_delay_seconds()

        captured = capsys.readouterr()
        # Should print delay info
        assert "[CHAOS DELAY]" in captured.out
        assert "Generated delay:" in captured.out


class TestGetFailureResponse:
    """Test get_failure_response() generation."""

    def test_basic_failure_response(self):
        """Test basic failure response structure."""
        config = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            seed=42
        )

        response = config.get_failure_response("inventory", "/check_stock")

        assert response["status"] == "error"
        assert response["error_type"] == "timeout"
        assert response["api"] == "inventory"
        assert response["endpoint"] == "/check_stock"
        assert "message" in response

    def test_timeout_response_includes_timeout_seconds(self):
        """Test that timeout response includes timeout_after_seconds."""
        config = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            max_delay_seconds=5,
            seed=42
        )

        response = config.get_failure_response("payments", "/capture")

        assert "timeout_after_seconds" in response
        assert response["timeout_after_seconds"] == 5

    def test_http_error_includes_status_code(self):
        """Test that http_error response includes http_code."""
        config = ChaosConfig(
            enabled=True,
            failure_type="http_error",
            seed=42
        )

        response = config.get_failure_response("erp", "/create_order")

        assert "http_code" in response
        assert response["http_code"] == 500

    def test_service_unavailable_includes_status_code(self):
        """Test that service_unavailable response includes http_code."""
        config = ChaosConfig(
            enabled=True,
            failure_type="service_unavailable",
            seed=42
        )

        response = config.get_failure_response("shipping", "/create_shipment")

        assert "http_code" in response
        assert response["http_code"] == 503

    def test_verbose_mode_prints_response(self, capsys):
        """Test that verbose mode prints failure response generation."""
        config = ChaosConfig(
            enabled=True,
            failure_type="timeout",
            seed=42,
            verbose=True  # ✅ Enable verbose
        )

        config.get_failure_response("inventory", "/check_stock")

        captured = capsys.readouterr()
        # Should print response info
        assert "[CHAOS RESPONSE]" in captured.out
        assert "api=inventory" in captured.out
        assert "failure_type=timeout" in captured.out


class TestResetRandomState:
    """Test reset_random_state() functionality."""

    def test_reset_produces_same_sequence(self):
        """Test that reset produces same random sequence."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            seed=42
        )

        # Generate first sequence
        sequence1 = [config.should_inject_failure() for _ in range(10)]

        # Reset and generate second sequence
        config.reset_random_state()
        sequence2 = [config.should_inject_failure() for _ in range(10)]

        # Should be identical
        assert sequence1 == sequence2

    def test_reset_without_seed(self):
        """Test that reset without seed works (doesn't crash)."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            seed=None  # No seed
        )

        # Should not crash
        config.reset_random_state()
        config.should_inject_failure()

    def test_verbose_mode_prints_reset(self, capsys):
        """Test that verbose mode prints reset info."""
        config = ChaosConfig(
            enabled=True,
            seed=42,
            verbose=True  # ✅ Enable verbose
        )

        config.reset_random_state()

        captured = capsys.readouterr()
        # Should print reset info
        assert "[CHAOS RESET]" in captured.out
        assert "seed=42" in captured.out


class TestCreateChaosConfigFactory:
    """Test create_chaos_config() factory function."""

    def test_factory_creates_enabled_config(self):
        """Test that factory always creates enabled config."""
        config = create_chaos_config(
            failure_type="timeout",
            failure_rate=0.3,
            max_delay=5,
            seed=42
        )

        assert config.enabled is True
        assert config.failure_rate == 0.3
        assert config.failure_type == "timeout"
        assert config.max_delay_seconds == 5
        assert config.seed == 42

    def test_factory_with_verbose(self):
        """Test that factory accepts verbose parameter."""
        config = create_chaos_config(
            failure_type="timeout",
            failure_rate=0.5,
            max_delay=3,
            seed=42,
            verbose=True  # ✅ NEW: Test verbose parameter
        )

        assert config.verbose is True

    def test_factory_validates_failure_rate(self):
        """Test that factory validates failure_rate range."""
        with pytest.raises(ValueError, match="failure_rate must be 0.0-1.0"):
            create_chaos_config(
                failure_type="timeout",
                failure_rate=1.5,  # Invalid
                max_delay=5
            )

        with pytest.raises(ValueError, match="failure_rate must be 0.0-1.0"):
            create_chaos_config(
                failure_type="timeout",
                failure_rate=-0.1,  # Invalid
                max_delay=5
            )

    def test_factory_validates_max_delay(self):
        """Test that factory validates max_delay is positive."""
        with pytest.raises(ValueError, match="max_delay must be > 0"):
            create_chaos_config(
                failure_type="timeout",
                failure_rate=0.5,
                max_delay=0  # Invalid
            )

        with pytest.raises(ValueError, match="max_delay must be > 0"):
            create_chaos_config(
                failure_type="timeout",
                failure_rate=0.5,
                max_delay=-1  # Invalid
            )

    def test_factory_validates_failure_type(self):
        """Test that factory validates failure_type."""
        with pytest.raises(ValueError, match="Invalid failure_type"):
            create_chaos_config(
                failure_type="invalid_type",  # Invalid
                failure_rate=0.5,
                max_delay=5
            )


class TestEqualityAndRepr:
    """Test __eq__ and __repr__ methods."""

    def test_equality_identical_configs(self):
        """Test that identical configs are equal."""
        config1 = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            failure_type="timeout",
            max_delay_seconds=3,
            seed=42,
            verbose=False  # ✅ Include verbose
        )

        config2 = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            failure_type="timeout",
            max_delay_seconds=3,
            seed=42,
            verbose=False  # ✅ Include verbose
        )

        assert config1 == config2

    def test_inequality_different_verbose(self):
        """Test that different verbose values make configs unequal."""
        config1 = ChaosConfig(enabled=True, verbose=False)
        config2 = ChaosConfig(enabled=True, verbose=True)

        assert config1 != config2  # ✅ NEW: Test verbose in equality

    def test_inequality_different_params(self):
        """Test that different params make configs unequal."""
        config1 = ChaosConfig(enabled=True, failure_rate=0.3)
        config2 = ChaosConfig(enabled=True, failure_rate=0.5)

        assert config1 != config2

    def test_repr_contains_all_fields(self):
        """Test that repr contains all config fields."""
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            failure_type="timeout",
            max_delay_seconds=3,
            seed=42,
            verbose=True  # ✅ Include verbose
        )

        repr_str = repr(config)

        assert "enabled=True" in repr_str
        assert "failure_rate=0.5" in repr_str
        assert "failure_type=timeout" in repr_str
        assert "max_delay_seconds=3" in repr_str
        assert "seed=42" in repr_str
        assert "verbose=True" in repr_str  # ✅ NEW: Test verbose in repr


class TestVerboseModeRegression:
    """Regression tests to ensure verbose mode doesn't break existing functionality."""

    def test_default_behavior_unchanged(self):
        """Test that default behavior (verbose=False) is unchanged."""
        # Old code (before verbose) should work identically
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.3,
            failure_type="timeout",
            max_delay_seconds=2,
            seed=42
            # No verbose parameter (defaults to False)
        )

        # All functionality should work
        assert config.should_inject_failure() in [True, False]
        assert config.get_delay_seconds() >= 0.0
        assert config.get_failure_response("api", "/endpoint") is not None

    def test_verbose_does_not_affect_randomness(self):
        """Test that verbose mode doesn't affect random behavior."""
        config_quiet = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            seed=42,
            verbose=False
        )

        config_verbose = ChaosConfig(
            enabled=True,
            failure_rate=0.5,
            seed=42,
            verbose=True
        )

        # Same seed should produce same results regardless of verbose
        results_quiet = [config_quiet.should_inject_failure() for _ in range(20)]
        results_verbose = [config_verbose.should_inject_failure() for _ in range(20)]

        assert results_quiet == results_verbose
