"""Real HTTP executor implementing the Executor protocol.

Replaces ChaosProxy for production use — sends real requests to
configurable base URLs with per-endpoint timeout support.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, Optional

import httpx

from chaos_engine.core.settings import DEFAULT_API_BASE_URL
from chaos_engine.core.types import Status

logger = logging.getLogger(__name__)


class HttpExecutor:
    """Production-grade HTTP executor satisfying the Executor protocol.

    Unlike ChaosProxy this executor does NOT inject failures — it forwards
    requests to the configured ``base_url`` and returns structured responses.

    Parameters
    ----------
    base_url:
        Base URL for all requests (e.g. ``https://petstore3.swagger.io/api/v3``).
    timeout:
        Default request timeout in seconds.
    seed:
        RNG seed for deterministic jittered backoff (optional).
    """

    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout: float = 10.0,
        seed: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._rng = random.Random(seed)
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle — reusable client (A.28: avoid per-request client creation)
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Executor protocol
    # ------------------------------------------------------------------

    async def send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json_body,
            )

            if response.status_code >= 400:
                logger.warning("API error %d on %s %s", response.status_code, method, endpoint)
                return {
                    "status": Status.ERROR,
                    "code": response.status_code,
                    "message": response.text[:500],
                }

            return {
                "status": Status.SUCCESS,
                "code": response.status_code,
                "data": response.json(),
            }

        except httpx.TimeoutException:
            logger.error("Timeout on %s %s", method, endpoint)
            return {"status": Status.ERROR, "code": 408, "message": "Request timed out"}

        except Exception as e:
            logger.error("Network error on %s %s: %s", method, endpoint, e)
            return {"status": Status.ERROR, "code": 500, "message": str(e)}

    def calculate_jittered_backoff(self, seconds: float) -> float:
        """Return *seconds* plus a random jitter component."""
        jitter = self._rng.random() * seconds * 0.5
        return seconds + jitter
