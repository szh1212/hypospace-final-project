# HypoSpace Final Project — EEC 4300

A four-person course project to design a novel machine learning method that helps LLMs generate multiple valid, distinct solutions on the HypoSpace benchmark.

## Hierarchical generation route (分层生成策略) on this branch

Branch `kevin/causal-main` develops the hierarchical route only: a-priori partitions of the admissible graph space with no coverage feedback and no representation change. Four generations of the method are covered by one results document:

- 父集分层 `parent_set`（第 1 代）→ 骨架补全 `skeleton_complete`（第 2 代）→
  强制骨架 `skeleton_complete_forced`（第 3 代）→
  **两级分层 + 有效性过滤 `skeleton_complete_forced_valid_joint`（第 4 代，最终方法）**。

Final test result (13 cases × 2 seeds × 16 calls): **V 91.35%, U 59.38%, R 56.66%** —
paired bootstrap CIs above zero for all three metrics versus every baseline, and all three
metrics above the SZH 3D baseline at its own budget (V 91.12% vs 78.52%, U 65.09% vs
21.65%, R 53.43% vs 17.45%).

All results, paired data, the four-generation history and the verification record live in one
document: [docs/experiment-results.md](docs/experiment-results.md).
All comparisons are paired on identical cases, seeds, sampling and budget; every raw call is
replayed and audited offline by the scripts in `experiments/`.

## Original main-branch scope

At the main-branch fork point the repository established the project structure and collaboration workflow. Candidate domains were causal graph inference, gravity-constrained 3D voxel reconstruction, and Boolean genetic interaction modeling; this branch works on the causal domain.

## HypoSpace evaluation

The benchmark evaluates sets of hypotheses using three complementary metrics:

| Metric | Meaning |
| --- | --- |
| Validity (V) | The proportion of generated proposals consistent with the observations and task constraints. |
| Uniqueness (U) | Non-redundancy among generated proposals: how well generation avoids repeated hypotheses. |
| Recovery (R) | Coverage of the enumerated admissible solution set by the distinct valid hypotheses recovered. |

## Repository layout

```text
README.md              Project overview and references
CONTRIBUTING.md        Four-person branch and PR workflow
src/                   Our own method code (strata, skeleton, validity filter)
experiments/           Frozen protocols, run and audit scripts
docs/                  Single experiment results and data document
```

## References

- Chen et al. (2026). *HypoSpace: A Diagnostic Benchmark for Set-Valued Hypothesis Generation under Underdetermination and Sublinear Coverage Bounds*. ICML, PMLR 306:15451–15465. [Paper](https://proceedings.mlr.press/v306/chen26bz.html).
- [Official HypoSpace code](https://github.com/CTT-Pavilion/_HypoSpace).

This is an independent EEC 4300 student project, not the official benchmark repository.
