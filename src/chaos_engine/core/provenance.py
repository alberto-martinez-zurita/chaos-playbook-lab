"""Data provenance tracking (Art. 10 EU AI Act — data governance, BK-017)."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DataClassification(StrEnum):
    """Data sensitivity classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DataProvenance:
    """Immutable record of where a piece of data came from."""

    source_uri: str
    sha256: str
    ingested_at: float
    classification: DataClassification
    metadata: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_sha256(data: str | bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# ProvenanceTracker
# ---------------------------------------------------------------------------

class ProvenanceTracker:
    """In-memory store for :class:`DataProvenance` records."""

    def __init__(self) -> None:
        self._records: list[DataProvenance] = []

    def record(self, provenance: DataProvenance) -> None:
        """Append a provenance record."""
        self._records.append(provenance)
        logger.debug("Recorded provenance: %s", provenance.source_uri)

    def get_by_source(self, source_uri: str) -> list[DataProvenance]:
        """Return all records matching *source_uri*."""
        return [r for r in self._records if r.source_uri == source_uri]

    def get_by_classification(self, classification: DataClassification) -> list[DataProvenance]:
        """Return all records matching *classification*."""
        return [r for r in self._records if r.classification == classification]

    def all_records(self) -> list[DataProvenance]:
        """Return a copy of every recorded provenance entry."""
        return list(self._records)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ProvenanceAware(Protocol):
    """Any object that optionally carries provenance metadata."""

    provenance: DataProvenance | None
