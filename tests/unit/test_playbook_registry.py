from __future__ import annotations

import json

import pytest

from chaos_engine.core.playbook_registry import (
    PlaybookMetadata,
    PlaybookRegistry,
    PlaybookStage,
    VersionedPlaybook,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_strategies() -> dict:
    return {
        "default": {"strategy": "fail_fast", "config": {}},
        "find_product": {"500": {"strategy": "retry_exponential_backoff", "config": {"base_delay": 1.0}}},
    }


def _make_playbook(version: str = "1.0.0", stage: str = PlaybookStage.DEV) -> VersionedPlaybook:
    return VersionedPlaybook(
        metadata=PlaybookMetadata(version=version, stage=stage, description="test"),
        strategies=_sample_strategies(),
    )


# ---------------------------------------------------------------------------
# VersionedPlaybook serialization
# ---------------------------------------------------------------------------

def test_round_trip_serialization(tmp_path):
    pb = _make_playbook()
    path = tmp_path / "pb.json"
    pb.save(path)

    loaded = VersionedPlaybook.from_file(path)
    assert loaded.metadata.version == "1.0.0"
    assert loaded.strategies["default"]["strategy"] == "fail_fast"


def test_to_dict_contains_metadata():
    pb = _make_playbook()
    d = pb.to_dict()
    assert "_metadata" in d
    assert d["_metadata"]["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Registry: register & get
# ---------------------------------------------------------------------------

def test_register_and_get(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    pb = _make_playbook("2.0.0")
    registry.register(pb)

    loaded = registry.get("2.0.0")
    assert loaded.metadata.version == "2.0.0"


def test_register_duplicate_raises(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    registry.register(_make_playbook("1.0.0"))
    with pytest.raises(FileExistsError):
        registry.register(_make_playbook("1.0.0"))


def test_get_nonexistent_raises(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    with pytest.raises(FileNotFoundError):
        registry.get("9.9.9")


def test_list_versions(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    registry.register(_make_playbook("1.0.0"))
    registry.register(_make_playbook("2.0.0"))
    registry.register(_make_playbook("1.1.0"))

    versions = registry.list_versions()
    assert len(versions) == 3
    assert "v1.0.0" in versions


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------

def test_promote_dev_to_lab(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    registry.register(_make_playbook("1.0.0", PlaybookStage.DEV))

    promoted = registry.promote("1.0.0", validated_by="ci")
    assert promoted.metadata.stage == PlaybookStage.LAB
    assert promoted.metadata.validated_by == "ci"


def test_promote_to_production_sets_current(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    registry.register(_make_playbook("1.0.0", PlaybookStage.STAGING))

    registry.promote("1.0.0", validated_by="admin")
    current = registry.get_current()
    assert current is not None
    assert current.metadata.version == "1.0.0"
    assert current.metadata.stage == PlaybookStage.PRODUCTION


def test_promote_rejects_below_min_success_rate(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    registry.register(_make_playbook("1.0.0", PlaybookStage.DEV))

    with pytest.raises(ValueError, match="Promotion rejected"):
        registry.promote(
            "1.0.0",
            min_success_rate=0.95,
            actual_success_rate=0.80,
        )


def test_promote_final_stage_raises(tmp_path):
    registry = PlaybookRegistry(tmp_path / "reg")
    registry.register(_make_playbook("1.0.0", PlaybookStage.PRODUCTION))

    with pytest.raises(ValueError, match="final stage"):
        registry.promote("1.0.0")


def test_full_lifecycle(tmp_path):
    """Promote from dev → lab → staging → production."""
    registry = PlaybookRegistry(tmp_path / "reg")
    registry.register(_make_playbook("3.0.0"))

    for expected_stage in [PlaybookStage.LAB, PlaybookStage.STAGING, PlaybookStage.PRODUCTION]:
        pb = registry.promote("3.0.0", validated_by="test")
        assert pb.metadata.stage == expected_stage
