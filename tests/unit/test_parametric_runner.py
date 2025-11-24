"""
Unit Tests for ParametricABTestRunner - PHASE 5.1 FIXED

Location: tests/unit/test_parametric_runner.py

Purpose: Unit tests for ParametricConfig and ParametricABTestRunner
         Validates configuration, path handling, and aggregation logic.

Test Coverage:
- ParametricConfig validation (valid/invalid rates)
- Results directory creation
- Path handling with custom project_root
- Mean and std calculation methods

FIX APPLIED:
  - Added time.sleep(1) in test_run_dir_unique_timestamp to prevent same-second collision
  - No other changes - preserves original test logic
"""

import pytest
import time  # ✅ ADDED: For timestamp uniqueness test
from pathlib import Path
from chaos_playbook_engine.experiments.parametric_runner import (
    ParametricConfig,
    ParametricABTestRunner
)


class TestParametricConfig:
    """Unit tests for ParametricConfig dataclass."""
    
    def test_valid_rates(self):
        """Test that valid failure rates are accepted."""
        config = ParametricConfig(
            failure_rates=[0.0, 0.5, 1.0],
            experiments_per_rate=10
        )
        assert len(config.failure_rates) == 3
        assert config.experiments_per_rate == 10
    
    def test_invalid_rate_too_high(self):
        """Test that failure rate > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="failure_rate must be in"):
            ParametricConfig(
                failure_rates=[0.0, 1.5],
                experiments_per_rate=10
            )
    
    def test_invalid_rate_negative(self):
        """Test that negative failure rate raises ValueError."""
        with pytest.raises(ValueError, match="failure_rate must be in"):
            ParametricConfig(
                failure_rates=[-0.1, 0.5],
                experiments_per_rate=10
            )
    
    def test_results_dir_creation(self, tmp_path):
        """Test that results directory is created automatically."""
        config = ParametricConfig(
            failure_rates=[0.0, 0.1],
            experiments_per_rate=5,
            project_root=tmp_path
        )
        
        # Check that results/parametric_experiments was created
        expected_dir = tmp_path / "results" / "parametric_experiments"
        assert expected_dir.exists()
        assert config.results_dir == expected_dir
    
    def test_custom_project_root(self, tmp_path):
        """Test that custom project_root is respected."""
        custom_root = tmp_path / "custom_project"
        custom_root.mkdir()
        
        config = ParametricConfig(
            failure_rates=[0.0],
            experiments_per_rate=1,
            project_root=custom_root
        )
        
        assert config.project_root == custom_root
        assert config.results_dir.parent.parent == custom_root


class TestParametricABTestRunner:
    """Unit tests for ParametricABTestRunner class."""
    
    def test_initialization(self, tmp_path):
        """Test that runner initializes with correct attributes."""
        config = ParametricConfig(
            failure_rates=[0.0, 0.1],
            experiments_per_rate=5,
            project_root=tmp_path
        )
        
        runner = ParametricABTestRunner(config)
        
        assert runner.config == config
        assert runner.run_dir.exists()
        assert runner.run_dir.parent == config.results_dir
        assert len(runner.all_results) == 0
    
    def test_run_dir_unique_timestamp(self, tmp_path):
        """Test that each runner creates unique timestamped directory.
        
        FIXED: Added time.sleep(1) to prevent same-second timestamp collision.
        """
        config = ParametricConfig(
            failure_rates=[0.0],
            experiments_per_rate=1,
            project_root=tmp_path
        )
        
        runner1 = ParametricABTestRunner(config)
        
        # ✅ FIXED: Wait 1 second to ensure different timestamp
        time.sleep(1)
        
        runner2 = ParametricABTestRunner(config)
        
        # Should have different directories
        assert runner1.run_dir != runner2.run_dir
        assert runner1.run_dir.exists()
        assert runner2.run_dir.exists()
    
    def test_mean_calculation(self):
        """Test _mean static method."""
        assert ParametricABTestRunner._mean([1.0, 2.0, 3.0]) == 2.0
        assert ParametricABTestRunner._mean([5.0]) == 5.0
        assert ParametricABTestRunner._mean([]) == 0.0
    
    def test_std_calculation(self):
        """Test _std static method."""
        # Sample: [1, 2, 3] -> mean=2, std=1.0
        std = ParametricABTestRunner._std([1.0, 2.0, 3.0])
        assert abs(std - 1.0) < 0.01
        
        # Single value -> std=0.0
        assert ParametricABTestRunner._std([5.0]) == 0.0
        
        # Empty list -> std=0.0
        assert ParametricABTestRunner._std([]) == 0.0
    
    def test_run_dir_naming_pattern(self, tmp_path):
        """Test that run_dir follows YYYYMMDD_HHMMSS pattern."""
        config = ParametricConfig(
            failure_rates=[0.0],
            experiments_per_rate=1,
            project_root=tmp_path
        )
        
        runner = ParametricABTestRunner(config)
        
        # Run dir should be: results/parametric_experiments/run_YYYYMMDD_HHMMSS
        dir_name = runner.run_dir.name
        assert dir_name.startswith("run_")
        assert len(dir_name) == 19  # "run_" + YYYYMMDD_HHMMSS (4+8+1+6)
