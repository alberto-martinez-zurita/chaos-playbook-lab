"""
Chaos injection helper functions for simulated APIs.

Location: src/chaos_playbook_engine/tools/chaos_injection_helper.py
Based on: ADR-006 Chaos Injection Points Architecture
Purpose: Centralized chaos error generation and injection logic
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Literal

from chaos_playbook_engine.config.chaos_config import ChaosConfig


async def inject_chaos_failure(
    api: str,
    endpoint: str,
    chaos_config: ChaosConfig,
    attempt: int = 1
) -> Dict[str, Any]:
    """
    Generate chaos-injected failure response.
    
    Centralizes chaos error generation logic for all APIs.
    Handles different failure types and returns standardized error responses.
    
    Args:
        api: Name of API (e.g., "inventory", "payments")
        endpoint: Endpoint called (e.g., "check_stock", "capture")
        chaos_config: ChaosConfig instance controlling failure type
        attempt: Attempt number (for debugging)
    
    Returns:
        Standardized error response dict
    
    Raises:
        ValueError: If chaos_config not enabled
    
    Examples:
        >>> config = ChaosConfig(
        ...     enabled=True,
        ...     failure_type="timeout",
        ...     max_delay_seconds=1,
        ...     seed=42
        ... )
        >>> result = await inject_chaos_failure("inventory", "check_stock", config)
        >>> result["status"]
        "error"
        >>> result["error_code"]
        "TIMEOUT"
        >>> result["retryable"]
        True
    """
    
    if not chaos_config.enabled:
        raise ValueError("chaos_config must have enabled=True")
    
    failure_type = chaos_config.failure_type
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    # ═════════════════════════════════════════════════════════════
    # TIMEOUT: Delay then return error
    # ═════════════════════════════════════════════════════════════
    
    if failure_type == "timeout":
        delay = chaos_config.get_delay_seconds()
        await asyncio.sleep(delay)
        
        return {
            "status": "error",
            "error_code": "TIMEOUT",
            "message": f"{api.title()} API request timed out after {delay:.1f}s",
            "retryable": True,
            "metadata": {
                "api": api,
                "endpoint": endpoint,
                "chaos_injected": True,
                "attempt": attempt,
                "timestamp": timestamp,
                "suggested_backoff_seconds": 2
            }
        }
    
    # ═════════════════════════════════════════════════════════════
    # SERVICE_UNAVAILABLE: 503 transient error
    # ═════════════════════════════════════════════════════════════
    
    elif failure_type == "service_unavailable":
        return {
            "status": "error",
            "error_code": "SERVICE_UNAVAILABLE",
            "message": f"{api.title()} API temporarily unavailable (503)",
            "retryable": True,
            "metadata": {
                "api": api,
                "endpoint": endpoint,
                "chaos_injected": True,
                "attempt": attempt,
                "timestamp": timestamp,
                "suggested_backoff_seconds": 4
            }
        }
    
    # ═════════════════════════════════════════════════════════════
    # INVALID_REQUEST: 400 permanent error
    # ═════════════════════════════════════════════════════════════
    
    elif failure_type == "invalid_request":
        return {
            "status": "error",
            "error_code": "INVALID_REQUEST",
            "message": f"Invalid request to {api} API ({endpoint})",
            "retryable": False,
            "metadata": {
                "api": api,
                "endpoint": endpoint,
                "chaos_injected": True,
                "attempt": attempt,
                "timestamp": timestamp
            }
        }
    
    # ═════════════════════════════════════════════════════════════
    # CASCADE: Multiple failures
    # ═════════════════════════════════════════════════════════════
    
    elif failure_type == "cascade":
        return {
            "status": "error",
            "error_code": "CASCADE_FAILURE",
            "message": f"Cascading failure detected in {api} API",
            "retryable": False,  # Cascade errors are not retryable
            "metadata": {
                "api": api,
                "endpoint": endpoint,
                "chaos_injected": True,
                "attempt": attempt,
                "timestamp": timestamp
            }
        }
    
    # ═════════════════════════════════════════════════════════════
    # PARTIAL: Partial success (mixed results)
    # ═════════════════════════════════════════════════════════════
    
    elif failure_type == "partial":
        return {
            "status": "error",
            "error_code": "PARTIAL_FAILURE",
            "message": f"Partial failure in {api} API ({endpoint}): Some operations succeeded, others failed",
            "retryable": True,
            "metadata": {
                "api": api,
                "endpoint": endpoint,
                "chaos_injected": True,
                "attempt": attempt,
                "timestamp": timestamp,
                "suggested_backoff_seconds": 2
            }
        }
    
    # ═════════════════════════════════════════════════════════════
    # DEFAULT: Unknown failure type
    # ═════════════════════════════════════════════════════════════
    
    else:
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": f"Unknown failure type: {failure_type}",
            "retryable": False,
            "metadata": {
                "api": api,
                "endpoint": endpoint,
                "chaos_injected": True,
                "attempt": attempt,
                "timestamp": timestamp
            }
        }


def is_retryable_error(error_response: Dict[str, Any]) -> bool:
    """
    Check if an error response is retryable.
    
    Args:
        error_response: Error response dict from API
    
    Returns:
        True if error has retryable=True, False otherwise
    
    Examples:
        >>> error = {
        ...     "status": "error",
        ...     "error_code": "TIMEOUT",
        ...     "retryable": True
        ... }
        >>> is_retryable_error(error)
        True
    """
    return error_response.get("retryable", False) is True


def get_suggested_backoff(error_response: Dict[str, Any]) -> int:
    """
    Get suggested backoff time from error response.
    
    Args:
        error_response: Error response dict from API
    
    Returns:
        Suggested backoff in seconds (default: 2)
    
    Examples:
        >>> error = {
        ...     "metadata": {"suggested_backoff_seconds": 4}
        ... }
        >>> get_suggested_backoff(error)
        4
    """
    return error_response.get("metadata", {}).get("suggested_backoff_seconds", 2)


def is_chaos_injected(error_response: Dict[str, Any]) -> bool:
    """
    Check if error was chaos-injected (for debugging).
    
    Args:
        error_response: Error response dict
    
    Returns:
        True if chaos_injected=True in metadata
    
    Examples:
        >>> error = {
        ...     "metadata": {"chaos_injected": True}
        ... }
        >>> is_chaos_injected(error)
        True
    """
    return error_response.get("metadata", {}).get("chaos_injected", False) is True
