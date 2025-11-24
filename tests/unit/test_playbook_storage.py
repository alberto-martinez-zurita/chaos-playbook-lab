"""
Unit tests for Chaos Playbook Storage and saveprocedure/loadprocedure tools.

Location: tests/unit/test_playbook_storage.py

Run with:
    poetry run pytest tests/unit/test_playbook_storage.py -v
"""

import asyncio
import json
import os
import pytest
from pathlib import Path
from datetime import datetime

from chaos_playbook_engine.data.playbook_storage import PlaybookStorage


# ==================================================================
# FIXTURES
# ==================================================================

@pytest.fixture
def test_playbook_path(tmp_path):
    """Provide temporary playbook file path."""
    return str(tmp_path / "test_chaos_playbook.json")


@pytest.fixture
async def storage(test_playbook_path):
    """Provide PlaybookStorage instance with test file."""
    return PlaybookStorage(file_path=test_playbook_path)


@pytest.fixture
async def populated_storage(test_playbook_path):
    """Provide storage with some test procedures."""
    storage = PlaybookStorage(file_path=test_playbook_path)
    
    # Add test procedures
    await storage.save_procedure(
        failure_type="timeout",
        api="inventory",
        recovery_strategy="Retry 3x with exponential backoff",
        success_rate=0.9
    )
    
    await storage.save_procedure(
        failure_type="service_unavailable",
        api="payments",
        recovery_strategy="Wait 4s then retry",
        success_rate=0.85
    )
    
    await storage.save_procedure(
        failure_type="timeout",
        api="inventory",
        recovery_strategy="Retry with linear backoff",
        success_rate=0.7
    )
    
    return storage


# ==================================================================
# TEST PLAYBOOK STORAGE CLASS
# ==================================================================

class TestPlaybookStorage:
    """Tests for PlaybookStorage class."""
    
    @pytest.mark.asyncio
    async def test_init_creates_directory_and_file(self, test_playbook_path):
        """Test initialization creates data directory and file."""
        # Ensure parent doesn't exist yet
        path = Path(test_playbook_path)
        if path.exists():
            path.unlink()
        if path.parent.exists():
            path.parent.rmdir()
        
        # Create storage
        storage = PlaybookStorage(file_path=test_playbook_path)
        
        # Verify directory and file created
        assert path.parent.exists()
        assert path.exists()
        
        # Verify file contains empty procedures
        with open(path, 'r') as f:
            data = json.load(f)
            assert data == {"procedures": []}
    
    @pytest.mark.asyncio
    async def test_save_procedure_creates_unique_id(self, storage):
        """Test saving procedure generates unique ID."""
        proc_id_1 = await storage.save_procedure(
            failure_type="timeout",
            api="inventory",
            recovery_strategy="Strategy 1",
            success_rate=0.9
        )
        
        proc_id_2 = await storage.save_procedure(
            failure_type="timeout",
            api="payments",
            recovery_strategy="Strategy 2",
            success_rate=0.8
        )
        
        assert proc_id_1 == "PROC-001"
        assert proc_id_2 == "PROC-002"
        assert proc_id_1 != proc_id_2
    
    @pytest.mark.asyncio
    async def test_save_procedure_persists_to_file(self, storage, test_playbook_path):
        """Test procedure is written to JSON file."""
        proc_id = await storage.save_procedure(
            failure_type="timeout",
            api="inventory",
            recovery_strategy="Retry 3x",
            success_rate=0.9,
            metadata={"test": "value"}
        )
        
        # Read file directly
        with open(test_playbook_path, 'r') as f:
            data = json.load(f)
        
        assert len(data["procedures"]) == 1
        proc = data["procedures"][0]
        assert proc["id"] == proc_id
        assert proc["failure_type"] == "timeout"
        assert proc["api"] == "inventory"
        assert proc["recovery_strategy"] == "Retry 3x"
        assert proc["success_rate"] == 0.9
        assert "created_at" in proc
        assert proc["metadata"] == {"test": "value"}
    
    @pytest.mark.asyncio
    async def test_save_procedure_validates_failure_type(self, storage):
        """Test invalid failure_type raises error."""
        with pytest.raises(ValueError, match="Invalid failure_type"):
            await storage.save_procedure(
                failure_type="invalid_type",
                api="inventory",
                recovery_strategy="Strategy",
                success_rate=0.9
            )
    
    @pytest.mark.asyncio
    async def test_save_procedure_validates_api(self, storage):
        """Test invalid api raises error."""
        with pytest.raises(ValueError, match="Invalid api"):
            await storage.save_procedure(
                failure_type="timeout",
                api="invalid_api",
                recovery_strategy="Strategy",
                success_rate=0.9
            )
    
    @pytest.mark.asyncio
    async def test_save_procedure_validates_success_rate(self, storage):
        """Test success_rate must be 0-1."""
        # Test < 0
        with pytest.raises(ValueError, match="Invalid success_rate"):
            await storage.save_procedure(
                failure_type="timeout",
                api="inventory",
                recovery_strategy="Strategy",
                success_rate=-0.1
            )
        
        # Test > 1
        with pytest.raises(ValueError, match="Invalid success_rate"):
            await storage.save_procedure(
                failure_type="timeout",
                api="inventory",
                recovery_strategy="Strategy",
                success_rate=1.5
            )
    
    @pytest.mark.asyncio
    async def test_load_procedures_all(self, populated_storage):
        """Test loading all procedures."""
        procedures = await populated_storage.load_procedures()
        
        assert len(procedures) == 3
        assert all("id" in p for p in procedures)
        assert all("failure_type" in p for p in procedures)
    
    @pytest.mark.asyncio
    async def test_load_procedures_filter_by_failure_type(self, populated_storage):
        """Test filtering by failure_type."""
        procedures = await populated_storage.load_procedures(
            failure_type="timeout"
        )
        
        assert len(procedures) == 2
        assert all(p["failure_type"] == "timeout" for p in procedures)
    
    @pytest.mark.asyncio
    async def test_load_procedures_filter_by_api(self, populated_storage):
        """Test filtering by api."""
        procedures = await populated_storage.load_procedures(
            api="inventory"
        )
        
        assert len(procedures) == 2
        assert all(p["api"] == "inventory" for p in procedures)
    
    @pytest.mark.asyncio
    async def test_load_procedures_filter_by_both(self, populated_storage):
        """Test filtering by both failure_type and api."""
        procedures = await populated_storage.load_procedures(
            failure_type="timeout",
            api="inventory"
        )
        
        assert len(procedures) == 2
        assert all(
            p["failure_type"] == "timeout" and p["api"] == "inventory"
            for p in procedures
        )
    
    @pytest.mark.asyncio
    async def test_get_best_procedure_highest_success_rate(self, populated_storage):
        """Test get_best_procedure returns highest success_rate."""
        # We have 2 timeout procedures for inventory:
        # - "Retry 3x with exponential backoff" (0.9)
        # - "Retry with linear backoff" (0.7)
        
        best = await populated_storage.get_best_procedure(
            failure_type="timeout",
            api="inventory"
        )
        
        assert best is not None
        assert best["success_rate"] == 0.9
        assert best["recovery_strategy"] == "Retry 3x with exponential backoff"
    
    @pytest.mark.asyncio
    async def test_get_best_procedure_not_found(self, populated_storage):
        """Test get_best_procedure returns None when not found."""
        best = await populated_storage.get_best_procedure(
            failure_type="network_error",
            api="shipping"
        )
        
        assert best is None
    
    @pytest.mark.asyncio
    async def test_thread_safety_concurrent_saves(self, storage):
        """Test concurrent saves don't corrupt file."""
        # Create multiple concurrent save tasks
        tasks = []
        for i in range(10):
            task = storage.save_procedure(
                failure_type="timeout",
                api="inventory",
                recovery_strategy=f"Strategy {i}",
                success_rate=0.8 + (i * 0.01)
            )
            tasks.append(task)
        
        # Execute concurrently
        proc_ids = await asyncio.gather(*tasks)
        
        # Verify all saved successfully
        assert len(proc_ids) == 10
        assert len(set(proc_ids)) == 10  # All unique
        
        # Verify all persisted
        procedures = await storage.load_procedures()
        assert len(procedures) == 10


# ==================================================================
# TEST SAVEPROCEDURE TOOL
# ==================================================================

class TestSaveprocedureTool:
    """Tests for saveprocedure tool."""
    
    @pytest.mark.asyncio
    async def test_saveprocedure_success(self, test_playbook_path, monkeypatch):
        """Test successful procedure save."""
        # Import saveprocedure tool
        # Note: This assumes saveprocedure is importable from order_orchestrator
        # If not yet integrated, this test will be skipped
        try:
            from chaos_playbook_engine.agents.order_orchestrator import saveprocedure
        except ImportError:
            pytest.skip("saveprocedure not yet integrated into order_orchestrator.py")
        
        # Mock PlaybookStorage to use test file
        original_init = PlaybookStorage.__init__
        
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        # Call saveprocedure
        result = await saveprocedure(
            failure_type="timeout",
            api="inventory",
            recovery_strategy="Retry 3x with backoff",
            success_rate=0.9
        )
        
        assert result["status"] == "success"
        assert "procedure_id" in result
        assert result["procedure_id"].startswith("PROC-")
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_saveprocedure_validates_failure_type(self, test_playbook_path, monkeypatch):
        """Test invalid failure_type returns error."""
        try:
            from chaos_playbook_engine.agents.order_orchestrator import saveprocedure
        except ImportError:
            pytest.skip("saveprocedure not yet integrated")
        
        # Mock storage
        original_init = PlaybookStorage.__init__
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        result = await saveprocedure(
            failure_type="invalid",
            api="inventory",
            recovery_strategy="Strategy",
            success_rate=0.9
        )
        
        assert result["status"] == "error"
        assert "Validation error" in result["message"]
    
    @pytest.mark.asyncio
    async def test_saveprocedure_validates_success_rate(self, test_playbook_path, monkeypatch):
        """Test success_rate must be 0-1."""
        try:
            from chaos_playbook_engine.agents.order_orchestrator import saveprocedure
        except ImportError:
            pytest.skip("saveprocedure not yet integrated")
        
        # Mock storage
        original_init = PlaybookStorage.__init__
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        result = await saveprocedure(
            failure_type="timeout",
            api="inventory",
            recovery_strategy="Strategy",
            success_rate=1.5
        )
        
        assert result["status"] == "error"
        assert "Validation error" in result["message"]


# ==================================================================
# TEST LOADPROCEDURE TOOL (NEW - PROMPT 2)
# ==================================================================

class TestLoadprocedureTool:
    """Tests for loadprocedure tool."""
    
    @pytest.mark.asyncio
    async def test_loadprocedure_found(self, test_playbook_path, monkeypatch):
        """Test loading existing procedure."""
        try:
            from chaos_playbook_engine.agents.order_orchestrator import saveprocedure, loadprocedure
        except ImportError:
            pytest.skip("loadprocedure not yet integrated")
        
        # Mock PlaybookStorage to use test file
        original_init = PlaybookStorage.__init__
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        # Setup: Save a procedure first
        await saveprocedure(
            failure_type="timeout",
            api="inventory",
            recovery_strategy="Retry 3x with exponential backoff",
            success_rate=0.9
        )
        
        # Test: Load it
        result = await loadprocedure(
            failure_type="timeout",
            api="inventory"
        )
        
        assert result["status"] == "success"
        assert "recovery_strategy" in result
        assert "Retry 3x" in result["recovery_strategy"]
        assert result["success_rate"] == 0.9
        assert "recommendation" in result
    
    @pytest.mark.asyncio
    async def test_loadprocedure_not_found(self, test_playbook_path, monkeypatch):
        """Test loading non-existent procedure."""
        try:
            from chaos_playbook_engine.agents.order_orchestrator import loadprocedure
        except ImportError:
            pytest.skip("loadprocedure not yet integrated")
        
        # Mock storage
        original_init = PlaybookStorage.__init__
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        result = await loadprocedure(
            failure_type="network_error",
            api="shipping"
        )
        
        assert result["status"] == "not_found"
        assert "message" in result
        assert "recommendation" in result
    
    @pytest.mark.asyncio
    async def test_loadprocedure_returns_best_procedure(self, test_playbook_path, monkeypatch):
        """Test returns highest success_rate when multiple exist."""
        try:
            from chaos_playbook_engine.agents.order_orchestrator import saveprocedure, loadprocedure
        except ImportError:
            pytest.skip("loadprocedure not yet integrated")
        
        # Mock storage
        original_init = PlaybookStorage.__init__
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        # Save 3 procedures with different success rates
        await saveprocedure("timeout", "inventory", "Strategy A", 0.7)
        await saveprocedure("timeout", "inventory", "Strategy B", 0.9)
        await saveprocedure("timeout", "inventory", "Strategy C", 0.8)
        
        result = await loadprocedure("timeout", "inventory")
        
        assert result["status"] == "success"
        assert "Strategy B" in result["recovery_strategy"]  # Highest
        assert result["success_rate"] == 0.9


# ==================================================================
# TEST PLAYBOOK INTEGRATION (NEW - PROMPT 2)
# ==================================================================

class TestPlaybookIntegration:
    """Integration tests for save/load cycle."""
    
    @pytest.mark.asyncio
    async def test_save_and_load_cycle(self, test_playbook_path, monkeypatch):
        """Test complete save → load cycle."""
        try:
            from chaos_playbook_engine.agents.order_orchestrator import saveprocedure, loadprocedure
        except ImportError:
            pytest.skip("Tools not yet integrated")
        
        # Mock storage
        original_init = PlaybookStorage.__init__
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        # Save procedure
        save_result = await saveprocedure(
            failure_type="service_unavailable",
            api="payments",
            recovery_strategy="Wait 4s then retry",
            success_rate=0.85
        )
        
        assert save_result["status"] == "success"
        proc_id = save_result["procedure_id"]
        
        # Load procedure
        load_result = await loadprocedure(
            failure_type="service_unavailable",
            api="payments"
        )
        
        assert load_result["status"] == "success"
        assert load_result["procedure_id"] == proc_id
        assert "Wait 4s" in load_result["recovery_strategy"]
        assert load_result["success_rate"] == 0.85
    
    @pytest.mark.asyncio
    async def test_load_updates_with_new_saves(self, test_playbook_path, monkeypatch):
        """Test that loading reflects newly saved procedures."""
        try:
            from chaos_playbook_engine.agents.order_orchestrator import saveprocedure, loadprocedure
        except ImportError:
            pytest.skip("Tools not yet integrated")
        
        # Mock storage
        original_init = PlaybookStorage.__init__
        def mock_init(self, file_path=None):
            original_init(self, file_path=test_playbook_path)
        monkeypatch.setattr(PlaybookStorage, "__init__", mock_init)
        
        # Initially, procedure not found
        result1 = await loadprocedure("rate_limit_exceeded", "erp")
        assert result1["status"] == "not_found"
        
        # Save new procedure
        await saveprocedure(
            failure_type="rate_limit_exceeded",
            api="erp",
            recovery_strategy="Exponential backoff with jitter",
            success_rate=0.95
        )
        
        # Now it should be found
        result2 = await loadprocedure("rate_limit_exceeded", "erp")
        assert result2["status"] == "success"
        assert "Exponential backoff" in result2["recovery_strategy"]
        assert result2["success_rate"] == 0.95


# ==================================================================
# TEST SUMMARY
# ==================================================================

"""
Expected Test Results (After Prompt 2):

TestPlaybookStorage: 13 tests
TestSaveprocedureTool: 3 tests
TestLoadprocedureTool: 3 tests (NEW - Prompt 2)
TestPlaybookIntegration: 2 tests (NEW - Prompt 2)

Total: 21 tests in test_playbook_storage.py

Run with:
    poetry run pytest tests/unit/test_playbook_storage.py -v
    # Expected: 21/21 passing (after integration)
"""
