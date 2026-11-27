# Task C: Boolean Genetic Interaction

Existing methods:

- [szh-baseline-genetic](szh-baseline-genetic/README.md)
- [Kevin hierarchical generation](kevin-boolean/experiment-results.md)

Published formal results (reported macro averages):

| Method | Validity | Uniqueness | Recovery | Calls |
| --- | ---: | ---: | ---: | ---: |
| SZH genetic | 14.35% | 8.76% | 2.98% | 270 |
| Kevin official-prompt control | 8.59% | 12.76% | 5.60% | 384 |
| Kevin one-hole skeleton + validity rescue | 100.00% | 35.94% | 53.69% | 384 |

Kevin's paired experiment uses 12 cases, seeds 17/42 and 16 calls per case and seed. Its final method partitions feasible truth-table completions, assigns one-hole expression skeletons and deterministically repairs leaf choices when needed. Scores include this validity rescue. Its official-prompt control uses the same cases, model, seeds, budget and evaluator.

Protocols differ across studies; paired comparisons require matched cases, seeds and budgets. Exact configurations, per-instance scores and archive availability are documented in the [SZH report](../../docs/baseline-all-domains/results.md), [Kevin comparison](kevin-boolean/experiment-results.md) and [detailed Boolean report](../../docs/boolean-experiment-results.md).
