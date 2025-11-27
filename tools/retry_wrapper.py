"""

Retry Wrapper with Chaos Playbook Integration - FIXED v2

Location: src/chaos_playbook_engine/tools/retry_wrapper.py

Purpose: Python-based retry logic with Chaos Playbook integration.

Enables deterministic, testable retry behavior while querying Playbook

for known recovery strategies.

Design: Uses asyncio.sleep for real delays (not mocked in tests).

Extracts backoff from strategy descriptions using regex patterns.

CHANGES (v2 - Nov 23, 2025):
- Changed backoff from exponential (2**attempt) to linear (1.0*attempt)
- Reduces latency overhead from ~80% to ~50%
- More predictable performance characteristics
- Sequence: 1s, 2s, 3s (instead of 2s, 4s, 8s)

"""

import asyncio

import re

from typing import Any, Callable, Dict, Optional

from storage.playbook_storage import PlaybookStorage

async def with_retry(

api_func: Callable,

api_name: str,

max_retries: int = 3,

*args,

**kwargs

) -> Dict[str, Any]:

    """

    Retry wrapper with Chaos Playbook integration.

    Args:

        api_func: API function to call (async)

        api_name: API name (inventory, payments, erp, shipping)

        max_retries: Maximum retry attempts (default 3)

        *args, **kwargs: Arguments for api_func

    Returns:

        API response dict

    Behavior:

        1. Call api_func

        2. If success: return result

        3. If retryable error: check Playbook for known strategy

        4. Apply backoff and retry

        5. On success: would call saveprocedure (via agent)

    Example:

        result = await with_retry(

            call_simulated_inventory_api,

            "inventory",

            endpoint="check_stock",

            payload={"sku": "WIDGET-A", "qty": 5}

        )

    """

    storage = PlaybookStorage()

    for attempt in range(1, max_retries + 1):

        # Call API

        result = await api_func(*args, **kwargs)

        # If successful, return

        if result.get("status") == "success":

            return result

        # If non-retryable, return error

        if not is_retryable_error(result):

            return result

        # If last attempt, return error

        if attempt >= max_retries:

            return result

        # Calculate backoff

        failure_type = result.get("error_code", "unknown").lower()

        # Check Playbook for known strategy

        procedure = await storage.get_best_procedure(

            failure_type=failure_type,

            api=api_name

        )

        if procedure:

            # Extract backoff from strategy description

            backoff = extract_backoff_from_strategy(

                procedure.get("recovery_strategy", "")

            )

        else:

            # ✅ FIXED: Linear backoff instead of exponential
            # Was: backoff = 2 ** attempt  (2s, 4s, 8s)
            # Now: backoff = 1.0 * attempt (1s, 2s, 3s)
            backoff = 1.0 * attempt

        # Apply backoff

        await asyncio.sleep(backoff)

    return result


def is_retryable_error(result: Dict[str, Any]) -> bool:

    """

    Check if error is retryable.

    Retryable errors:

    - TIMEOUT (transient network issue)

    - SERVICE_UNAVAILABLE (temporary overload)

    - RATE_LIMIT_EXCEEDED (back off and retry)

    Non-retryable errors:

    - INVALID_REQUEST (bad input)

    - NOT_FOUND (resource doesn't exist)

    Args:

        result: API result dict with error_code

    Returns:

        True if retryable, False otherwise

    """

    retryable = {"TIMEOUT", "SERVICE_UNAVAILABLE", "RATE_LIMIT_EXCEEDED"}

    error_code = result.get("error_code", "").upper()

    return result.get("retryable", False) or error_code in retryable


def extract_backoff_from_strategy(strategy: str) -> float:

    """

    Extract backoff time from strategy description.

    Looks for patterns like:

    - "2s" → 2.0

    - "4 seconds" → 4.0

    - "exponential backoff (2s, 4s, 8s)" → uses first: 2.0

    Args:

        strategy: Recovery strategy description (free text)

    Returns:

        Backoff time in seconds (default 2.0 if not found)

    Example:

        extract_backoff_from_strategy("Retry with 3s delay") → 3.0

        extract_backoff_from_strategy("Unknown strategy") → 2.0

    """

    # Try to find pattern like "Ns" where N is a number

    match = re.search(r'(\d+\.?\d*)\s*s(?:econds?)?', strategy.lower())

    if match:

        try:

            return float(match.group(1))

        except:

            pass

    # Default

    return 2.0


# ==================================================================

# HELPER: Check if error was chaos-injected

# ==================================================================

def is_chaos_injected(result: Dict[str, Any]) -> bool:

    """

    Check if error was injected by chaos system.

    Chaos-injected errors have "chaos_injected" flag set.

    Args:

        result: API result dict

    Returns:

        True if chaos-injected

    """

    return result.get("chaos_injected", False)
