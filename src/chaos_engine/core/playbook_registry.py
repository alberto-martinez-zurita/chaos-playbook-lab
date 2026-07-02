"""Playbook Registry — versioned lifecycle management for playbooks.

Supports Dev → Lab → Staging → Production promotion with validation gates.
Each playbook version is stored as a separate JSON file with metadata.
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PlaybookStage(StrEnum):
    """Lifecycle stages for playbook promotion."""
    DEV = "dev"
    LAB = "lab"
    STAGING = "staging"
    PRODUCTION = "production"


# Promotion order: dev → lab → staging → production
_PROMOTION_ORDER = list(PlaybookStage)


@dataclass(frozen=True, slots=True)
class PlaybookMetadata:
    """Immutable metadata envelope for a versioned playbook."""
    version: str
    stage: str = PlaybookStage.DEV
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validated_by: str | None = None
    description: str = ""
    parent_version: str | None = None


@dataclass
class VersionedPlaybook:
    """A playbook with its metadata and strategy content."""
    metadata: PlaybookMetadata
    strategies: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "_metadata": asdict(self.metadata),
            **self.strategies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VersionedPlaybook:
        meta_raw = data.pop("_metadata", {})
        metadata = PlaybookMetadata(**meta_raw) if meta_raw else PlaybookMetadata(version="0.0.0")
        return cls(metadata=metadata, strategies=data)

    @classmethod
    def from_file(cls, path: str | Path) -> VersionedPlaybook:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Saved playbook v%s to %s", self.metadata.version, path)


class PlaybookRegistry:
    """Manages multiple versioned playbooks with lifecycle promotion.

    Directory layout::

        registry_dir/
          v1.0.0.json
          v1.1.0.json
          v2.0.0.json
          current.json  (symlink or copy of the active version)
    """

    def __init__(self, registry_dir: str | Path) -> None:
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def register(self, playbook: VersionedPlaybook) -> Path:
        """Register a new playbook version. Returns the saved file path."""
        version = playbook.metadata.version
        path = self._version_path(version)
        if path.exists():
            raise FileExistsError(f"Version {version} already exists at {path}")
        playbook.save(path)
        logger.info("Registered playbook v%s (stage=%s)", version, playbook.metadata.stage)
        return path

    def get(self, version: str) -> VersionedPlaybook:
        """Load a specific version."""
        path = self._version_path(version)
        if not path.exists():
            raise FileNotFoundError(f"Version {version} not found at {path}")
        return VersionedPlaybook.from_file(path)

    def list_versions(self) -> list[str]:
        """Return all registered version strings, sorted."""
        versions = [
            p.stem for p in sorted(self.registry_dir.glob("v*.json"))
        ]
        return versions

    def get_current(self) -> VersionedPlaybook | None:
        """Load the current active playbook (if set)."""
        current_path = self.registry_dir / "current.json"
        if not current_path.exists():
            return None
        return VersionedPlaybook.from_file(current_path)

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def promote(
        self,
        version: str,
        validated_by: str = "system",
        min_success_rate: float | None = None,
        actual_success_rate: float | None = None,
    ) -> VersionedPlaybook:
        """Promote a playbook to the next lifecycle stage.

        If ``min_success_rate`` is provided, the playbook is rejected
        unless ``actual_success_rate >= min_success_rate``.
        """
        playbook = self.get(version)
        current_stage = PlaybookStage(playbook.metadata.stage)
        current_idx = _PROMOTION_ORDER.index(current_stage)

        if current_idx >= len(_PROMOTION_ORDER) - 1:
            raise ValueError(f"Playbook v{version} is already at {current_stage} (final stage)")

        # Validation gate
        if min_success_rate is not None and actual_success_rate is not None:
            if actual_success_rate < min_success_rate:
                raise ValueError(
                    f"Promotion rejected: success_rate {actual_success_rate:.2%} "
                    f"< required {min_success_rate:.2%}"
                )

        next_stage = _PROMOTION_ORDER[current_idx + 1]

        promoted = VersionedPlaybook(
            metadata=PlaybookMetadata(
                version=version,
                stage=next_stage,
                created_at=playbook.metadata.created_at,
                validated_by=validated_by,
                description=playbook.metadata.description,
                parent_version=playbook.metadata.parent_version,
            ),
            strategies=playbook.strategies,
        )

        # Overwrite the version file with updated stage
        promoted.save(self._version_path(version))

        # If promoted to production, update current.json
        if next_stage == PlaybookStage.PRODUCTION:
            self._set_current(version)

        logger.info(
            "Promoted v%s: %s → %s (validated_by=%s)",
            version, current_stage, next_stage, validated_by,
        )
        return promoted

    def _set_current(self, version: str) -> None:
        """Copy the version file to current.json."""
        src = self._version_path(version)
        dst = self.registry_dir / "current.json"
        shutil.copy2(src, dst)
        logger.info("Set current playbook to v%s", version)

    def _version_path(self, version: str) -> Path:
        # Ensure version string starts with 'v'
        if not version.startswith("v"):
            version = f"v{version}"
        return self.registry_dir / f"{version}.json"
