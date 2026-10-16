**Table 3 — Excluded / partial models.**

These models appear in the dataset but are excluded from the main comparative figures (all comparative figures) because their coverage or failure mode is qualitatively different from the active roster. Listed here as appendix evidence.

| Model | Total params | Active | Reason for exclusion |
|---|---|---|---|
| gpt_oss_20b | 21B | 3.6B | Reproducible degenerate decoding loop ('?' tokens) at rate 0.20 (§3.6); rates 0.00–0.20 preserved as qualitative evidence of high-chaos breakdown but not comparable with the rest of the roster (different N + truncated rates). |
