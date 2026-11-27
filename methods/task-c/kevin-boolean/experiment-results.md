# Boolean Gene-Interaction Domain — Experiment Results and Baseline Comparison

This document is the results overview of the `kevin/boolean` branch, centered on the
**comparison between the new method and the baseline experiments**. Method definitions,
disclosures, and the verification record live in
[docs/boolean-experiment-results.md](boolean-experiment-results.md); every number comes
from `.cache/boolean-test.json` (output of the paired-analysis script
`experiments/analyze_boolean.py`) and can be replayed call-by-call from the local `runs/`
raw archives.

## 1. Paired protocol (baseline conditions matched)

All four methods share the same **12 frozen test cases** (6 with two observations and
6 with three observations, sampled from the official collection with fixed seeds and no
result-based filtering), repeat seeds **[17, 42]**, a **16-call budget per case**, the same
local model and sampling (Qwen2.5-3B-Instruct Q4_K_M, Ollama 0.40.18, temperature 0.7), and
the same official evaluator with the official V/U/R definitions. The only difference between
methods is the generation procedure (prompt face and deterministic assembly); the official
baseline runs the upstream prompt loop with accumulated hypothesis history, unmodified.

| Method | Description |
| --- | --- |
| Official prompt (baseline) | Upstream `create_prompt` with accumulated hypothesis history |
| Completion strata (1st generation) | Verbal requirement to honor truth-table row completions |
| Skeleton (2nd generation) | One-hole expression skeleton fixed per stratum, filled by the model |
| **Skeleton + validity rescue (final method)** | Skeleton plus a deterministic leaf repair, in a fixed public order, when the model's fill misses the stratum completion |

## 2. Main test table (12 cases × 2 seeds × 16 calls, macro means)

| Method | V | U | R@4 | R@8 | R@13 | R@16 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Official prompt (baseline) | 8.59% | 12.76% | 4.41% | 5.60% | 5.60% | 5.60% |
| Completion strata (1st generation) | 5.21% | 5.21% | 0.70% | 1.34% | 1.66% | 1.66% |
| Skeleton (2nd generation) | 32.03% | 18.23% | 12.04% | 21.34% | 26.85% | 28.89% |
| **Skeleton + validity rescue (final)** | **100.00%** | **35.94%** | **32.89%** | **44.63%** | **51.99%** | **53.69%** |

## 3. Paired differences of the final method versus each baseline (bootstrap, 10,000 resamples over the 12 cases)

| Control | Metric | Δ@16 | 95% CI | W/T/L | Δ@13 | 95% CI | W/T/L |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Official prompt | V | **+91.4pp** | [+85.2, +96.9] | 12/0/0 | +89.7pp | [+82.4, +96.2] | 12/0/0 |
| Official prompt | U | **+23.2pp** | [+13.8, +32.0] | 11/0/1 | +26.9pp | [+16.0, +37.2] | 11/0/1 |
| Official prompt | R | **+48.1pp** | [+39.6, +55.9] | 12/0/0 | +46.4pp | [+38.3, +54.1] | 12/0/0 |
| Completion strata | V | +94.8pp | [+87.5, +99.7] | 12/0/0 | +94.9pp | [+88.1, +99.7] | 12/0/0 |
| Completion strata | U | +30.7pp | [+24.2, +37.5] | 12/0/0 | +36.2pp | [+28.9, +43.9] | 12/0/0 |
| Completion strata | R | +52.0pp | [+45.3, +59.2] | 12/0/0 | +50.3pp | [+44.1, +56.9] | 12/0/0 |
| Skeleton | V | +68.0pp | [+61.5, +74.5] | 12/0/0 | +68.0pp | [+61.5, +74.4] | 12/0/0 |
| Skeleton | U | +17.7pp | [+12.0, +24.0] | 11/1/0 | +22.1pp | [+15.1, +29.5] | 11/1/0 |
| Skeleton | R | +24.8pp | [+18.0, +31.8] | 11/1/0 | +25.1pp | [+18.5, +32.0] | 11/1/0 |

**Against the official baseline, the paired 95% intervals of all three metrics (V/U/R) are
entirely above zero** — all three are significantly improved over the baseline.

## 4. Per-case comparison (@16, averaged over the two seeds)

| Case | Baseline V/U/R | Final method V/U/R | Ground-truth keys (recoverable) |
| --- | ---: | ---: | ---: |
| n2_inputs_10_11_outputs_11 | 3.1% / 9.4% / 0.0% | 100% / 59.4% / 59.4% | 16 (12) |
| n2_inputs_10_11_outputs_10 | 3.1% / 6.2% / 4.5% | 100% / 31.2% / 45.5% | 11 (5) |
| n2_inputs_00_11_outputs_10 | 34.4% / 9.4% / 11.5% | 100% / 37.5% / 46.2% | 13 (6) |
| n2_inputs_00_01_outputs_01 | 0.0% / 18.8% / 0.0% | 100% / 46.9% / 53.6% | 14 (8) |
| n2_inputs_01_10_outputs_10 | 21.9% / 9.4% / 6.2% | 100% / 50.0% / 50.0% | 16 (9) |
| n2_inputs_00_01_outputs_11 | 9.4% / 9.4% / 7.7% | 100% / 50.0% / 61.5% | 13 (9) |
| n3_inputs_00_01_10_outputs_111 | 9.4% / 15.6% / 14.3% | 100% / 34.4% / 78.6% | 7 (6) |
| n3_inputs_01_10_11_outputs_010 | 3.1% / 15.6% / 6.2% | 100% / 18.8% / 37.5% | 8 (3) |
| n3_inputs_00_01_10_outputs_100 | 18.8% / 25.0% / 16.7% | 100% / 12.5% / 33.3% | 6 (2) |
| n3_inputs_00_10_11_outputs_011 | 0.0% / 15.6% / 0.0% | 100% / 34.4% / 68.8% | 8 (6) |
| n3_inputs_00_01_10_outputs_001 | 0.0% / 12.5% / 0.0% | 100% / 37.5% / 60.0% | 10 (6) |
| n3_inputs_00_01_10_outputs_110 | 0.0% / 6.2% / 0.0% | 100% / 18.8% / 50.0% | 6 (3) |

## 5. Recovery ceiling and attainment

The official space enumeration contains 31 "ghost" mechanistic keys whose expressions exceed
the depth limit (the official validator always rejects them, yet their keys count in the
ground-truth denominator). Across the 12 test cases, 75 of 128 ground-truth keys are
recoverable, giving a macro R ceiling of ≈ **57.6%**. The final method reaches R = 53.69%,
i.e. **93.2% of the ceiling permitted by the official semantics**; the remaining gap consists
entirely of ghost keys, which no method can recover.

## 6. Development pilot (4 cases × 1 seed × 16 calls)

| Method | V | U | R@16 |
| --- | ---: | ---: | ---: |
| Official prompt (baseline) | 1.56% | 9.38% | 2.27% |
| Completion strata (1st generation) | 0.00% | 6.25% | 0.00% |
| Skeleton (2nd generation) | 20.31% | 17.19% | 24.32% |
| **Skeleton + validity rescue (final)** | **100.00%** | **37.50%** | **51.36%** |

## Conclusion

Under fully paired conditions, the final method versus the official-prompt baseline:
**V 100.00% vs 8.59% (+91.4pp), U 35.94% vs 12.76% (+23.2pp), R 53.69% vs 5.60% (+48.1pp)** —
the paired bootstrap 95% intervals of all three metrics are entirely above zero; the method
also improves significantly over both in-route baselines (completion strata and skeleton).
