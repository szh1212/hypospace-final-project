# HypoSpace Final Project — EEC 4300

A four-person course project to design a novel machine learning method that helps LLMs generate multiple valid, distinct solutions on the HypoSpace benchmark.

## Hierarchical generation route (分层生成策略) on this branch

Branch `kevin/causal-main` develops the hierarchical route only: a-priori partitions of the admissible graph space with no coverage feedback and no representation change.

1. **Parent-set strata** (`parent_set`): cycle over the exact incoming edges of the most ambiguous anchor. Test R@16 19.07% vs official 1.11%, edge_count 12.66%, unstratified 14.74%. [Results](docs/parent-strata-results.md) · [Test report](docs/parent-strata-test.json)
2. **Skeleton completion** (`skeleton_complete`): the stratum parents are fixed structurally and the model completes only the remaining edges. Test R@16 19.78%; beats edge_count +7.12pp with 10 wins 0 losses (CI [+3.5, +11.6]). [Results](docs/parent-skeleton-results.md) · [Test report](docs/parent-skeleton-test.json)
3. **Forced-backbone skeleton** (`skeleton_complete_forced`): additionally fixes every necessary-condition forced edge and enforces the edge budget in assembly. Test R@16 **31.53%** — vs official +30.41pp with 13/13 wins (CI [+15.4, +48.5]), vs parent_set +12.46pp (CI [+5.9, +20.2]), vs skeleton_complete +11.75pp (CI [+1.7, +27.7]); the budget-only ablation ties skeleton_complete on all 13 cases, so the gain is entirely attributable to the forced backbone. Aligned to the SZH baseline budget (13 calls per case, seeds 17/42/2026) it reaches R@13 **32.08%** vs SZH 17.45%. [Results](docs/parent-skeleton-results.md) · [Aligned-budget results](docs/budget-aligned-results.md) · [Route summary](docs/hierarchical-route.md)

All comparisons are paired on identical cases, seeds, sampling and budget; every raw call is replayed and audited offline (see [verification](docs/verification.md)). The other two routes — coverage-feedback adaptive generation and spatial/action representation transformation — are out of scope for this branch and only appear as context in the earlier study below.

## Causal experiment on this branch

Branch `kevin/causal-main` starts at main commit `2c24720`. A matched Qwen2.5-3B test on eight causal intervention cases raised recovery from 0.13% with the official prompt to 21.51% with fixed structural rotation and 21.52% with adaptive scheduling. [Results](docs/causal-results.md) · [Protocol and reproduction](docs/causal-methods.md)

## Original main-branch scope

At the main-branch fork point the repository established the project structure and collaboration workflow. The table records its decisions at that time.

| Decision | Status |
| --- | --- |
| Target domain / task family | TBD |
| Model(s) | TBD |
| Proposed method | TBD |
| Experimental protocol and budget | TBD |
| Results | TBD — no measurements yet |

Candidate domains are causal graph inference, gravity-constrained 3D voxel reconstruction, and Boolean genetic interaction modeling. The team will choose the domain, models, and approach together before running experiments.

## HypoSpace evaluation

The benchmark evaluates sets of hypotheses using three complementary metrics:

| Metric | Meaning |
| --- | --- |
| Validity (V) | The proportion of generated proposals consistent with the observations and task constraints. |
| Uniqueness (U) | Non-redundancy among generated proposals: how well generation avoids repeated hypotheses. |
| Recovery (R) | Coverage of the enumerated admissible solution set by the distinct valid hypotheses recovered. |

We will follow the official evaluator's definitions, canonicalization, and aggregation for the selected domain. A good method should expand coverage and reduce repetition while maintaining validity; evaluation details and comparison budgets are TBD.

## Repository layout

```text
README.md              Project overview and references
CONTRIBUTING.md        Four-person branch and PR workflow
src/                   Our own method code (placeholder)
experiments/           Experiment configurations and run scripts (placeholder)
docs/                  Project plan, task ownership, and experiment records
.gitignore             Exclusions for secrets and generated / large artifacts
```

The official implementation is linked below only. We have not copied it, added a submodule, installed dependencies, downloaded data, or selected an integration strategy. Decide how to integrate it after agreeing on the experimental plan, and record the upstream revision used.

## First steps for teammates

1. Accept the repository owner's GitHub collaborator invitation.
2. Read this README and [CONTRIBUTING.md](CONTRIBUTING.md), then clone the repository.
3. Create your own branch from the latest `main` and claim one of the four tasks in [docs/project-plan.md](docs/project-plan.md) through a PR.
4. Request review from another teammate. Agree on the domain, model, method, and budget before starting experiments.

Keep credentials in local environment variables or an ignored `.env` file. Commit only small, reviewed summaries; keep weights, datasets, and raw outputs outside Git.

## References

- Chen et al. (2026). *HypoSpace: A Diagnostic Benchmark for Set-Valued Hypothesis Generation under Underdetermination and Sublinear Coverage Bounds*. ICML, PMLR 306:15451–15465. [Paper](https://proceedings.mlr.press/v306/chen26bz.html).
- [Official HypoSpace code](https://github.com/CTT-Pavilion/_HypoSpace).

This is an independent EEC 4300 student project, not the official benchmark repository.
