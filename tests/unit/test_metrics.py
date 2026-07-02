import pytest
from chaos_engine.reporting.aggregate_metrics import MetricsAggregator
# Necesitamos simular la dataclass ExperimentResult
from dataclasses import dataclass, field
from typing import List

@dataclass
class MockResult:
    outcome: str
    total_duration_s: float
    inconsistencies: List[str] = field(default_factory=list)
    playbook_strategies_used: List[str] = field(default_factory=list)

def test_consistency_calculation():
    agg = MetricsAggregator()
    
    # 3 Inconsistentes, 7 Consistentes
    results = [
        MockResult("inconsistent", 1.0, ["erp_fail"]),
        MockResult("inconsistent", 1.0, ["shipping_fail"]),
        MockResult("inconsistent", 1.0, ["erp_fail"]),
        MockResult("success", 1.0),
        MockResult("success", 1.0),
        MockResult("success", 1.0),
        MockResult("success", 1.0),
        MockResult("success", 1.0),
        MockResult("failure", 1.0), # Fallo pero consistente
        MockResult("failure", 1.0)  # Fallo pero consistente
    ]
    
    metrics = agg.calculate_consistency_rate(results)
    
    assert metrics["sample_size"] == 10
    assert metrics["inconsistent_count"] == 3
    assert metrics["consistent_count"] == 7
    assert metrics["consistency_rate"] == 0.7
    assert metrics["inconsistency_types"]["erp_fail"] == 2

def test_latency_statistics():
    agg = MetricsAggregator()
    # Tiempos: 1, 2, 3, 4, 100 (outlier)
    results = [
        MockResult("success", 1.0),
        MockResult("success", 2.0),
        MockResult("success", 3.0),
        MockResult("success", 4.0),
        MockResult("success", 100.0),
    ]
    
    stats = agg.calculate_latency_stats(results)
    
    assert stats["min_latency_s"] == 1.0
    assert stats["max_latency_s"] == 100.0
    assert stats["median_latency_s"] == 3.0
    assert stats["mean_latency_s"] == 22.0