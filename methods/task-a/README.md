# Task A: Causal Graph Inference

Existing methods:

- [szh-baseline-causal](szh-baseline-causal/README.md)
- [Kevin hierarchical generation](kevin-causal-graph/experiment-results.md)

Published formal results (reported macro averages):

| Method | Validity | Uniqueness | Recovery | Calls |
| --- | ---: | ---: | ---: | ---: |
| SZH causal | 5.05% | 24.66% | 0.37% | 654 |
| Kevin official-prompt control | 23.08% | 6.49% | 1.11% | 416 |
| Kevin two-level stratification + validity filter | 91.35% | 59.38% | 56.66% | 416 |

Kevin's paired experiment uses 13 cases, seeds 17/42 and 16 calls per case and seed. Its final method fixes parent sets for two nodes, preserves mandatory edges and filters model-proposed additions. Scores include deterministic assembly and filtering. The table reproduces the final report's published values; the report and branch audit scripts describe scoring and replay.

The SZH row uses the 654-call unified subset. The complete causal batch contains 2,019 calls including a separate alignment cohort. Protocols differ across studies; paired comparisons require matched cases, seeds and budgets. Exact configurations, per-instance scores and archive availability are documented in the [SZH report](../../docs/baseline-all-domains/results.md) and [Kevin report](kevin-causal-graph/experiment-results.md).
