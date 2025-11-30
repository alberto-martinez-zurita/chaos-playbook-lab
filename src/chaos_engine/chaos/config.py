"""
Chaos injection configuration for simulated APIs.

Location: src/chaos_playbook_engine/config/chaos_config.py

Based on: ADR-005 & ADR-006

Purpose: Configure when/how failures are injected during testing

DEBUG VERSION (Nov 23, 2025) - VERBOSE MODE ADDED:
- Added verbose parameter (default: False)
- All existing print() now conditional on self.verbose
- Preserved ALL original functionality exactly
- Use --verbose flag in CLI to enable debugging

"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Optional, Literal
from datetime import datetime


@dataclass
class ChaosConfig:
    """
    Configuration for chaos injection in simulated APIs.

    Controls when and how failures are injected during testing.
    Uses seed-based randomness for deterministic scenarios.

    Attributes:
        enabled: Whether chaos injection is active
        failure_rate: Probability of failure (0.0 to 1.0)
        failure_type: Type of failure to inject
        max_delay_seconds: Maximum delay for timeout scenarios
        seed: Random seed for deterministic behavior (None = random)
        verbose: Enable detailed chaos logging (default: False)  # ✅ NEW
    """
    enabled: bool = False
    failure_rate: float = 0.0
    failure_type: Literal["timeout", "service_unavailable", "invalid_request", "cascade", "partial", "http_error"] = "timeout"
    max_delay_seconds: int = 2
    seed: Optional[int] = None
    verbose: bool = False  # ✅ NEW: Default OFF
    
    # Private: random instance for deterministic behavior
    _random_instance: random.Random = field(default_factory=random.Random, init=False, repr=False)

    def get_assets_dir(self) -> str:
        """Get the assets directory path."""
        return "assets"

    def __post_init__(self):
        """Initialize random instance after dataclass creation."""
        # Set seed if provided
        if self.seed is not None:
            self._random_instance.seed(self.seed)

        # ✅ CHANGED: Only print if verbose=True
        if self.verbose:
            print(f"\n[CHAOS INIT] Creating ChaosConfig:")
            print(f"  enabled={self.enabled}")
            print(f"  failure_rate={self.failure_rate}")
            print(f"  failure_type={self.failure_type}")
            print(f"  max_delay_seconds={self.max_delay_seconds}")
            print(f"  seed={self.seed}")
            print(f"  verbose={self.verbose}")  # ✅ NEW
            print(f"  ✅ Random instance created with seed={self.seed}\n")

    def should_inject_failure(self) -> bool:
        """
        Determine if a failure should be injected for this API call.

        Uses seed-based randomness for deterministic test scenarios.
        """
        if not self.enabled:
            return False

        # Early exit for edge cases
        if self.failure_rate >= 1.0:
            if self.verbose:  # ✅ CHANGED
                print(f"[CHAOS CHECK] failure_rate >= 1.0 → ALWAYS FAIL")
            return True

        if self.failure_rate <= 0.0:
            if self.verbose:  # ✅ CHANGED
                print(f"[CHAOS CHECK] failure_rate <= 0.0 → NEVER FAIL")
            return False

        # Generate random value
        random_value = self._random_instance.random()
        inject = random_value < self.failure_rate

        # ✅ CHANGED: Only print debug info if verbose mode is ON
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[CHAOS CHECK {timestamp}] should_inject_failure()")
            print(f"  enabled={self.enabled}")
            print(f"  failure_rate={self.failure_rate}")
            print(f"  random_value={random_value:.6f}")
            print(f"  inject={inject} ({'✓ CHAOS INJECTED' if inject else '✗ no chaos'})")

        return inject

    def get_delay_seconds(self) -> float:
        """
        Get delay in seconds for timeout scenarios.

        Returns:
            Random delay between 1 and max_delay_seconds (seed-controlled).
            Returns 0.0 if failure_type is not "timeout".
        """
        if self.failure_type != "timeout":
            return 0.0

        delay = self._random_instance.uniform(1.0, float(self.max_delay_seconds))

        if self.verbose:  # ✅ CHANGED
            print(f"[CHAOS DELAY] Generated delay: {delay:.2f}s (range: 1.0-{self.max_delay_seconds}s)")

        return delay

    def get_failure_response(self, api_name: str, endpoint: str) -> dict:
        """
        Generate appropriate failure response based on failure_type.

        Args:
            api_name: Name of the API (e.g., "inventory", "payments")
            endpoint: API endpoint path

        Returns:
            Dictionary with failure response structure
        """
        response = {
            "status": "error",
            "error_type": self.failure_type,
            "message": f"Simulated chaos: {self.failure_type}",
            "api": api_name,
            "endpoint": endpoint
        }

        # Add failure-type specific fields
        if self.failure_type == "timeout":
            response["timeout_after_seconds"] = self.max_delay_seconds
        elif self.failure_type == "http_error":
            response["http_code"] = 500
        elif self.failure_type == "service_unavailable":
            response["http_code"] = 503

        # ✅ CHANGED: Only print failure info if verbose mode is ON
        if self.verbose:
            print(f"[CHAOS RESPONSE] Generated failure response:")
            print(f"  api={api_name}")
            print(f"  endpoint={endpoint}")
            print(f"  failure_type={self.failure_type}")

        return response

    def reset_random_state(self):
        """
        Reset the random instance to its initial seed state.

        Useful for repeating exact same chaos scenario in tests.
        """
        if self.seed is not None:
            self._random_instance.seed(self.seed)

        # ✅ CHANGED: Only print reset info if verbose mode is ON
        if self.verbose:
            print(f"[CHAOS RESET] Random state reset to seed={self.seed}")

    def __eq__(self, other):
        """Compare ChaosConfig objects (excluding _random_instance)."""
        if not isinstance(other, ChaosConfig):
            return False
        return (
            self.enabled == other.enabled
            and self.failure_rate == other.failure_rate
            and self.failure_type == other.failure_type
            and self.max_delay_seconds == other.max_delay_seconds
            and self.seed == other.seed
            and self.verbose == other.verbose  # ✅ NEW
        )

    def __repr__(self):
        """String representation for debugging."""
        return (
            f"ChaosConfig("
            f"enabled={self.enabled}, "
            f"failure_rate={self.failure_rate}, "
            f"failure_type={self.failure_type}, "
            f"max_delay_seconds={self.max_delay_seconds}, "
            f"seed={self.seed}, "
            f"verbose={self.verbose}"  # ✅ NEW
            f")"
        )


# ✅ Factory function for backwards compatibility
def create_chaos_config(
    failure_type: str,
    failure_rate: float = 1.0,
    max_delay: int = 5,
    seed: Optional[int] = None,
    verbose: bool = False  # ✅ NEW
) -> ChaosConfig:
    """
    Factory function to create ChaosConfig with validation.

    Args:
        failure_type: Type of failure
        failure_rate: Probability (0.0-1.0)
        max_delay: Max delay for timeouts
        seed: Random seed
        verbose: Enable verbose logging (default: False)  # ✅ NEW

    Returns:
        Configured ChaosConfig instance

    Raises:
        ValueError: If parameters invalid
    """
    if not 0.0 <= failure_rate <= 1.0:
        raise ValueError(f"failure_rate must be 0.0-1.0, got {failure_rate}")

    if max_delay <= 0:
        raise ValueError(f"max_delay must be > 0, got {max_delay}")

    valid_types = {"timeout", "service_unavailable", "invalid_request", "cascade", "partial", "http_error"}
    if failure_type not in valid_types:
        raise ValueError(f"Invalid failure_type. Must be one of {valid_types}")

    return ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,
        failure_type=failure_type,
        max_delay_seconds=max_delay,
        seed=seed,
        verbose=verbose  # ✅ NEW
    )