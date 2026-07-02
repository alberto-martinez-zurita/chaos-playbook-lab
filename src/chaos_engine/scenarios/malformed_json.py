"""Scenario: Malformed JSON returns from tool calls."""
from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from chaos_engine.scenarios.base import ChaosScenario

logger = logging.getLogger(__name__)


class MalformationType(StrEnum):
    """Kinds of JSON malformation injected by the scenario."""

    TRUNCATED = "truncated"
    WRONG_TYPES = "wrong_types"
    MISSING_FIELDS = "missing_fields"
    ENCODING_ERROR = "encoding_error"
    EMPTY = "empty"


_MALFORMED_PAYLOADS: dict[MalformationType, str] = {
    MalformationType.TRUNCATED: '{"result": "he',
    MalformationType.WRONG_TYPES: '{"id": "not_an_int", "items": "should_be_list"}',
    MalformationType.MISSING_FIELDS: "{}",
    MalformationType.ENCODING_ERROR: '{"data": "caf\\udce9"}',
    MalformationType.EMPTY: "",
}


@runtime_checkable
class JSONConsumer(Protocol):
    """Agent that receives a raw JSON string and processes it."""

    async def process_json(self, raw: str) -> dict[str, Any]: ...


class MalformedJSONScenario(ChaosScenario):
    """Returns various malformed JSON payloads from tool calls and verifies
    the agent does not crash and provides fallback behaviour.
    """

    def __init__(
        self,
        consumer: JSONConsumer,
        *,
        malformations: list[MalformationType] | None = None,
    ) -> None:
        self._consumer = consumer
        self._malformations = malformations or list(MalformationType)

    @property
    def name(self) -> str:
        return "malformed_json"

    @property
    def description(self) -> str:
        return f"Inject {len(self._malformations)} types of malformed JSON"

    async def setup(self) -> None:
        pass

    async def execute(self) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for kind in self._malformations:
            payload = _MALFORMED_PAYLOADS[kind]
            try:
                resp = await self._consumer.process_json(payload)
                results.append({"type": str(kind), "crashed": False, "response": resp})
            except Exception as exc:  # noqa: BLE001
                logger.warning("Consumer crashed on %s: %s", kind, exc)
                results.append({"type": str(kind), "crashed": True, "error": str(exc)})
        return {"results": results}

    async def verify(self, execution_data: dict[str, Any]) -> bool:
        results = execution_data.get("results", [])
        if not results:
            return False
        crashes = [r for r in results if r.get("crashed")]
        if crashes:
            logger.error("%d/%d malformations caused crashes", len(crashes), len(results))
            return False
        return True

    async def teardown(self) -> None:
        pass
