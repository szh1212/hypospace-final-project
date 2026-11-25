# Experiment log

2026-11-25 — Completed the matched causal study on `kevin/causal-main`.
The 7 Qwen methods used 2,016 real local calls. The uniform graph-edit control used 288 symbolic selections.
See [results](causal-results.md), [protocol](causal-methods.md), and [test evidence](causal-test.json).

2026-11-25 — Parent-set stratification (hierarchical route) on a fresh 17-type split.
1,920 real calls (dev 256, test 1,664) all replayed and audited against independent reachability checks.
Test R@16 19.07% vs official 1.11%, edge_count 12.66%, unstratified 14.74%.
See [results](parent-strata-results.md), [dev report](parent-strata-dev.json), [test report](parent-strata-test.json).

2026-11-25 — Hierarchical skeleton completion (structural stratum enforcement) frozen for test.
Dev pilot (128 real calls): skeleton_complete R 18.34% vs parent_set 13.36% and enforce-only 9.79%;
the complete variant was frozen before any test inference.
See [design and dev decision](parent-skeleton-results.md), [dev report](parent-skeleton-dev.json).

For each future run, add a small summary using this template. Store raw artifacts outside Git and link their agreed shared location without exposing credentials.

```text
Run ID and date:
Owner:
Purpose / hypothesis:
Project commit and official benchmark commit:
Environment / dependency versions:
Domain, dataset provenance, and task sizes:
Model/provider and version:
Method / baseline:
Configuration path and exact command:
Seeds, decoding settings, and sample/query budget:
Metric definitions and aggregation:
Validity / Uniqueness / Recovery:
Runtime and compute/API cost:
Raw artifact location:
Failures / limitations:
Interpretation and next step:
```
