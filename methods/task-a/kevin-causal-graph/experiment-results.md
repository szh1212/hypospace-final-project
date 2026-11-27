# Experiment Results and Data — Hierarchical Generation, Causal Graph Inference

This is the single results-and-data document for the causal-domain hierarchical
generation route developed on branch `kevin/causal-main`; it replaces the earlier
per-study markdown and JSON reports and is archived here under
`methods/task-a/kevin-causal-graph/` on `main`. All results come from real calls of a
local Qwen2.5-3B-Instruct Q4_K_M (Ollama 0.40.18, temperature 0.7) against the official
HypoSpace causal benchmark (upstream commit `c69e931`); evaluation uses the official
parser and the official V/U/R definitions. Raw calls and responses are kept locally
under `runs/` on the branch machine (excluded from Git by convention); every number in
this document can be replayed and checked against those raw records with the audit
scripts in `experiments/` on the `kevin/causal-main` branch.

---

## 1. Final method: two-level stratification + validity filter (`skeleton_complete_forced_valid_joint`)

On top of the forced-backbone skeleton (third generation), the method adds two
mechanisms that remain on the **hierarchical generation** route:

1. **Two-level stratification**: besides fixing the anchor's parent set, each stratum
   also fixes the feasible parent set of a second node (necessary-condition closure
   plus acyclicity check), rotating across both levels. Every call targets a finer
   structural region, so cross-stratum repetition is structurally impossible.
2. **Validity filter**: each model-added edge is accepted greedily in output order,
   keeping only the subset under which the union stays acyclic, within the edge budget
   and free of unwanted reachability. Already-valid proposals are reproduced exactly
   (V and R can only stay or rise per cell); the valid subset of invalid proposals is
   rescued.

Difference from the other two routes: no recovered solution is ever read (the
stratification is fully a priori), the graph representation is unchanged (official
edge-list output plus deterministic union/filtering), and there is no action selection
or backtracking search.

### 1.1 Main test table (13 cases × 2 seeds × 16 calls, macro averages)

| Method | V | U | R@4 | R@8 | R@16 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Official prompt (baseline) | 23.08% | 6.49% | 1.11% | 1.11% | 1.11% |
| Unstratified, same wording (baseline) | 61.30% | 10.34% | 14.26% | 14.74% | 14.74% |
| Edge-count strata (baseline) | 39.90% | 16.11% | 12.21% | 12.21% | 12.66% |
| Parent-set strata (gen 1) | 50.24% | 27.40% | 15.44% | 16.27% | 19.07% |
| Skeleton completion (gen 2) | 50.00% | 32.45% | 16.69% | 18.83% | 19.78% |
| Forced backbone (gen 3) | 68.99% | 32.93% | 28.63% | 30.87% | 31.53% |
| Validity filter (gen-4 ablation) | 85.10% | 29.81% | 29.44% | 31.60% | 32.36% |
| **Two-level joint + validity filter (final)** | **91.35%** | **59.38%** | **36.34%** | **47.34%** | **56.66%** |

### 1.2 Paired deltas of the final method versus each baseline (@16, 2 seeds, bootstrap over 13 cases, 10,000 resamples)

| Final method − control | ΔV | ΔU | ΔR |
| --- | ---: | ---: | ---: |
| Official prompt | +68.3pp [+43.0, +87.7] | +52.9pp [+35.6, +70.7] | +55.6pp [+40.5, +70.6] (13/13 wins) |
| Unstratified | +30.1pp [+6.0, +54.3] | +49.0pp [+31.5, +66.8] | +41.9pp [+29.7, +53.7] |
| Edge-count strata | +51.4pp [+32.7, +69.5] | +43.3pp [+25.5, +61.1] | +44.0pp [+30.1, +58.2] |
| Parent-set strata | +41.1pp [+24.8, +56.3] | +32.0pp [+18.3, +45.9] | +37.6pp [+25.2, +50.4] |

The paired intervals at the @13 budget are likewise all above zero (ΔR vs official
prompt +52.9pp [+37.4, +68.3], 13/13 wins; vs parent-set strata +34.9pp [+22.9, +47.3]).

### 1.3 Direct comparison with the SZH 3D baseline (aligned budget: 13 calls per case, repeat seeds 17/42/2026)

The SZH baseline numbers come from its branch `origin/szh/baseline-3d`,
`docs/figures/baseline/metrics.json` (585 calls, macro V=78.52%, U=21.65%, R=17.45%;
archived on main under `methods/task-b/szh-baseline-3d`). The comparison below is a
cross-domain side-by-side reference (different tasks, no paired intervals; the
within-domain paired evidence is in 1.2):

| Method (3 seeds, R@13) | V | U | R |
| --- | ---: | ---: | ---: |
| SZH baseline (3D domain) | 78.52% | 21.65% | 17.45% |
| Forced backbone (gen 3) | 71.79% | 41.03% | 32.08% |
| Validity filter (ablation) | 86.00% | 36.29% | 33.07% |
| **Two-level joint + validity filter (final)** | **91.12%** | **65.09%** | **53.43%** |
| Final method − SZH | +12.60pp | +43.44pp | +35.98pp |

All three metrics exceed the SZH baseline.

### 1.4 Four generations (paired protocol: same cases, seeds and budget)

| Gen | Method | Mechanism | Dev R@16 | Test R@16 |
| --- | --- | --- | ---: | ---: |
| 1 | Parent-set strata `parent_set` | The model is asked verbally to respect the anchor's parent-set stratum | 13.36% | 19.07% |
| 2 | Skeleton completion `skeleton_complete` | The stratum's parent edges are fixed by the system; the model completes the rest | 18.34% | 19.78% |
| 3 | Forced backbone `skeleton_complete_forced` | All necessary-condition forced edges are fixed too, plus budget enforcement | 21.91% | 31.53% |
| 4 | Two-level joint + validity filter `skeleton_complete_forced_valid_joint` | Second node's feasible parent set fixed per stratum + greedy validity filtering | **59.30%** (V 71.88%, U 65.62%) | **56.66%** (V 91.35%, U 59.38%) |

Attribution: the validity filter alone lifts V from 68.99% to 85.10% (+16.1pp), R +0.8pp,
U roughly flat; the two-level stratification then lifts U to 59.38% (+29.6pp), R to
56.66% (+24.3pp) and V by another +6.3pp.

### 1.5 Per-case results of the final method (@16, macro averages)

| Case | V | U | R (2 seeds) | R (3 seeds @16) |
| --- | ---: | ---: | ---: | ---: |
| n1_017 | 100.00% | 100.00% | 9.76% | 9.76% |
| n1_024 | 50.00% | 96.88% | 15.31% | 17.01% |
| n1_030 | 84.38% | 84.38% | 39.66% | 39.08% |
| n2_017 | 100.00% | 100.00% | 34.78% | 34.78% |
| n2_033 | 100.00% | 6.25% | 100.00% | 100.00% |
| n2_049 | 100.00% | 43.75% | 63.64% | 63.64% |
| n2_054 | 71.88% | 46.88% | 85.71% | 71.43% |
| n2_069 | 100.00% | 25.00% | 57.14% | 57.14% |
| n2_098 | 81.25% | 59.38% | 72.73% | 75.76% |
| n2_112 | 100.00% | 28.12% | 56.25% | 58.33% |
| n2_126 | 100.00% | 93.75% | 40.54% | 40.54% |
| n2_140 | 100.00% | 18.75% | 100.00% | 100.00% |
| n2_186 | 100.00% | 68.75% | 61.11% | 61.11% |

## 2. Earlier study (context)

- The eight-case causal study (`causal-main.json` protocol, Qwen2.5-3B): official prompt
  R 0.13% → fixed structural rotation 21.51%, adaptive scheduling 21.52%
  (coverage-feedback route), legal edit menu 46.84% (model-chosen actions, the
  representation-transformation route; random choice with backtracking 59.49%).
  That study used different case IDs and only serves as route background.
- Coverage-feedback adaptation and representation transformation are the other two
  routes; they are not part of the method documented here.

## 3. Verifiability

- **Unit tests**: `python3 -m unittest discover -s tests` (43 tests covering the
  properties of stratification, forced edges, two-level strata, union, budget
  enforcement and the validity filter).
- **Per-call offline audit**: `experiments/analyze_*.py` replays every call from
  `runs/*/raw`, independently checking the prompts, stratum rotation, union/filtering,
  prefix V/U/R and summary consistency. Audit sizes: parent-set strata 1,920 calls,
  skeleton completion 416 calls, forced backbone 832 calls, budget-aligned 507 cells,
  generation 4 78 cells (1,248 records). All pass.
- **Run-level replay**: every `run_parent_skeleton.py --replay` compares each cell
  against the recorded summary; the generation-4 dev and test replays pass.
- **Freezing and disclosures**: protocols and code were frozen and committed before
  inference (parent-set strata `372fa66`, skeleton completion `8786caa`, forced
  backbone `c14245e`, budget alignment `4fee1bd`, generation 4 `87c0d8d`). After the
  generation-4 test inference, the audit found a missing acyclicity check in the
  second-level enumeration (some strata fixed cyclic edge sets); after the fix, 138
  affected records were regenerated with the same seeds and budget while the rest were
  reused verbatim, and the whole run was re-audited. The test cases were reused across
  the generations (matching the "not strictly unseen" disclosure of the baseline
  repository for its test set); no method or sampling hyperparameter was adjusted on
  the basis of test results.
- **Raw data location**: model calls and responses live locally under `runs/` on the
  branch machine (excluded from Git by convention); the official benchmark is pinned
  locally at `.cache/hypospace` (upstream commit `c69e931`).
