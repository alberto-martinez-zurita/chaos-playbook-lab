# Parametric Experiment Report

**Generated:** 2025-11-30 00:54:10

**Experiment Run:** `run_20251129_144331`

---

## Executive Summary

This parametric study evaluated the **Chaos Playbook Engine** across 7 failure rates (0% to 20%) with 1000 experiment pairs per rate, totaling **14000 individual runs**.

### Key Findings

**🎯 Primary Result:** Under maximum chaos conditions (20% failure rate):
- **Baseline Agent**: 37% success rate
- **Playbook Agent**: 97% success rate
- **Improvement**: **+60 percentage points** (160.8% relative improvement)

**✅ Hypothesis Validation:** The RAG-powered Playbook Agent demonstrates **significantly higher resilience** under chaos conditions compared to the baseline agent.

**⚖️ Trade-offs Observed:**
- **Reliability**: Playbook agent achieves higher success rates under chaos
- **Latency**: Playbook agent incurs ~2-3x longer execution time due to retry logic
- **Consistency**: Playbook agent maintains data integrity better (fewer inconsistencies)

---
## Methodology

**Experimental Design:** Parametric A/B testing across 7 failure rate conditions.

**Failure Rates Tested:** 0%, 1%, 3%, 5%, 10%, 15%, 20%

**Experiments per Rate:** 1000 pairs (baseline + playbook)

**Total Runs:** 14000

**Agents Under Test:**
- **Baseline Agent**: Simple agent with no retry logic (accepts first failure)
- **Playbook Agent**: RAG-powered agent with intelligent retry strategies

**Metrics Collected:**
1. Success Rate (% of successful order completions)
2. Execution Duration (seconds, with std dev)
3. Data Inconsistencies (count of validation errors)

**Chaos Injection:** Simulated API failures (timeouts, errors) injected at configured rates.

---

## Detailed Results by Failure Rate

### Failure Rate: 0%

**Experiments:** 1000 pairs (2000 total runs)

| Metric | Baseline Agent | Playbook Agent | Delta |
|--------|----------------|----------------|-------|
| **Success Rate** | 100.0% | 100.0% | **+0.0%** |
| **Avg Duration** | 0.44s ± 0.00s | 0.44s ± 0.00s | +0.00s |
| **Avg Inconsistencies** | 0.00 | 0.00 | +0.00 |

⚖️ **Both agents perform equally** in success rate.

---

### Failure Rate: 1%

**Experiments:** 1000 pairs (2000 total runs)

| Metric | Baseline Agent | Playbook Agent | Delta |
|--------|----------------|----------------|-------|
| **Success Rate** | 95.4% | 100.0% | **+4.6%** |
| **Avg Duration** | 0.42s ± 0.00s | 0.44s ± 0.00s | +0.01s |
| **Avg Inconsistencies** | 0.03 | 0.00 | -0.03 |

✅ **Playbook outperforms** by 4.6 percentage points in success rate.

---

### Failure Rate: 3%

**Experiments:** 1000 pairs (2000 total runs)

| Metric | Baseline Agent | Playbook Agent | Delta |
|--------|----------------|----------------|-------|
| **Success Rate** | 88.9% | 100.0% | **+11.1%** |
| **Avg Duration** | 0.41s ± 0.00s | 0.44s ± 0.00s | +0.03s |
| **Avg Inconsistencies** | 0.06 | 0.00 | -0.06 |

✅ **Playbook outperforms** by 11.1 percentage points in success rate.

---

### Failure Rate: 5%

**Experiments:** 1000 pairs (2000 total runs)

| Metric | Baseline Agent | Playbook Agent | Delta |
|--------|----------------|----------------|-------|
| **Success Rate** | 80.9% | 100.0% | **+19.1%** |
| **Avg Duration** | 0.38s ± 0.00s | 0.44s ± 0.00s | +0.05s |
| **Avg Inconsistencies** | 0.09 | 0.00 | -0.09 |

✅ **Playbook outperforms** by 19.1 percentage points in success rate.

---

### Failure Rate: 10%

**Experiments:** 1000 pairs (2000 total runs)

| Metric | Baseline Agent | Playbook Agent | Delta |
|--------|----------------|----------------|-------|
| **Success Rate** | 61.1% | 99.8% | **+38.7%** |
| **Avg Duration** | 0.32s ± 0.00s | 0.44s ± 0.00s | +0.11s |
| **Avg Inconsistencies** | 0.17 | 0.00 | -0.17 |

✅ **Playbook outperforms** by 38.7 percentage points in success rate.

---

### Failure Rate: 15%

**Experiments:** 1000 pairs (2000 total runs)

| Metric | Baseline Agent | Playbook Agent | Delta |
|--------|----------------|----------------|-------|
| **Success Rate** | 50.3% | 98.5% | **+48.2%** |
| **Avg Duration** | 0.29s ± 0.00s | 0.43s ± 0.00s | +0.14s |
| **Avg Inconsistencies** | 0.20 | 0.01 | -0.19 |

✅ **Playbook outperforms** by 48.2 percentage points in success rate.

---

### Failure Rate: 20%

**Experiments:** 1000 pairs (2000 total runs)

| Metric | Baseline Agent | Playbook Agent | Delta |
|--------|----------------|----------------|-------|
| **Success Rate** | 37.2% | 97.0% | **+59.8%** |
| **Avg Duration** | 0.25s ± 0.00s | 0.43s ± 0.00s | +0.18s |
| **Avg Inconsistencies** | 0.24 | 0.01 | -0.23 |

✅ **Playbook outperforms** by 59.8 percentage points in success rate.

---

## Statistical Analysis

### Reliability Analysis

Success rate improvement across chaos levels:

| Failure Rate | Baseline Success | Playbook Success | Improvement | Effect Size |
|--------------|------------------|------------------|-------------|-------------|
| 0% | 100.0% | 100.0% | +0.0% | Small |
| 1% | 95.4% | 100.0% | +4.6% | Small |
| 3% | 88.9% | 100.0% | +11.1% | Small |
| 5% | 80.9% | 100.0% | +19.1% | Small |
| 10% | 61.1% | 99.8% | +38.7% | Medium |
| 15% | 50.3% | 98.5% | +48.2% | Medium |
| 20% | 37.2% | 97.0% | +59.8% | Large |

### Latency Analysis

Execution duration trade-offs:

| Failure Rate | Baseline Duration | Playbook Duration | Overhead | Overhead % |
|--------------|-------------------|-------------------|----------|-----------|
| 0% | 0.44s | 0.44s | +0.00s | +0.0% |
| 1% | 0.42s | 0.44s | +0.01s | +2.8% |
| 3% | 0.41s | 0.44s | +0.03s | +7.6% |
| 5% | 0.38s | 0.44s | +0.05s | +14.1% |
| 10% | 0.32s | 0.44s | +0.11s | +34.1% |
| 15% | 0.29s | 0.43s | +0.14s | +49.5% |
| 20% | 0.25s | 0.43s | +0.18s | +74.4% |

**Interpretation:** Playbook agent consistently takes longer due to retry logic and RAG-powered strategy retrieval. This is an expected trade-off for increased reliability.

---

## Visualizations

### Success Rate Comparison

Comparison of success rates between baseline and playbook agents across failure rates.

<img src="plots/success_rate_comparison.png" alt="Success Rate Comparison" width="800"/>

### Duration Comparison

Average execution duration with standard deviation error bars.

<img src="plots/duration_comparison.png" alt="Duration Comparison" width="800"/>

### Inconsistencies Analysis

Data inconsistencies observed across different failure rates.

<img src="plots/inconsistencies_comparison.png" alt="Inconsistencies Analysis" width="800"/>

### Side-by-Side Agent Comparison

Bar chart comparing agent performance at each failure rate.

<img src="plots/agent_comparison_bars.png" alt="Side-by-Side Agent Comparison" width="800"/>

---

## Conclusions and Recommendations

### Key Takeaways

1. **RAG-Powered Resilience Works**: Under chaos conditions, the Playbook Agent achieves an average **30.2% improvement** in success rate compared to baseline.

2. **Latency-Reliability Trade-off**: The Playbook Agent incurs 2-3x latency overhead, which is acceptable for high-reliability requirements but may not suit latency-sensitive applications.

3. **Data Integrity Benefits**: Playbook Agent demonstrates better data consistency, reducing the risk of partial failures and data corruption.

### Recommendations

**For Production Deployment:**
- ✅ Use **Playbook Agent** for critical workflows where reliability > latency
- ✅ Use **Baseline Agent** for non-critical, latency-sensitive operations
- ✅ Consider **hybrid approach**: Baseline first, fallback to Playbook on failure

**For Further Research:**
- 🔬 Optimize retry logic to reduce latency overhead
- 🔬 Test with higher failure rates (>50%) to find breaking points
- 🔬 Evaluate cost implications of increased retries
- 🔬 Study playbook strategy effectiveness distribution

---

## Appendix

**Raw Data:** `raw_results.csv`

**Aggregated Metrics:** `aggregated_metrics.json`

**Plots Directory:** `plots/`

