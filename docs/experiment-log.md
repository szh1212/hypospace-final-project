# Experiment log

## 2026-11-25 offline verification

Completed 585 uniform-height random proposals through the pinned official 3D evaluator. No LLM calls and no API spending. This validates plumbing, not LLM performance or the proposed methods.

Command: `python src/hypospace_runner.py --mode offline --out runs/offline-v1`
Plot command: `python src/plot_results.py runs/offline-v1/summary.json --out docs/figures/offline`
Upstream: c69e9318577b34b5b896996571aefd4ba6053f58.
Dataset SHA256 and fixed dev/test IDs: experiments/manifest.json.
Python, host, runner source SHA256, resolved control model and settings: offline-control-summary.json. Dependency pins: requirements.txt. Full raw responses and results: ignored runs/offline-v1/ (local only).

Overall macro V=1.000000, U=0.651029, R=0.651029. Results are from a uniform random height sampler, not an LLM. Each occupied column is independently sampled uniformly from heights 1..3. As every sampled structure is valid and Q=|H|, final U equals R. A second complete run reproduced the same aggregate values after adding cache-resumption handling.

Validation: four unit tests pass for duplicate/invalid/parse-failure metric denominators, trailing-zero normalization, gravity, and the known official maximum-height validation gap. Python compilation passes. Curve figure visually inspected. No claim of learned-model determinism is made.

## 2026-11-25 real Qwen smoke test

Model locked to Qwen2.5-3B-Instruct Q4_K_M, digest 357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b, Ollama 0.40.18. CPU i5-1155G7, four inference threads, Python 3.12, SSD environment. Zero commercial API usage.

Command: `python src/hypospace_runner.py --smoke --out C:/Users/宋知恒/HypoSpaceLocal/runs/smoke`

Three dev observations g3_h3_b1_009, g3_h3_b2_013, g3_h3_b3_084; seed17; three proposals each; temperature0.7, top_p0.9, top_k40, max_tokens512, context8192, repeat_penalty1.0. Nine outputs, all parseable, zero valid and zero recovered. U across tasks = 1, 2/3, 1 (macro0.888889). Input/output tokens=6888/903. Sum of call wall times=206.526249 seconds, mean22.947 seconds. No output hit the token cap. All raw JSON is retained on SSD; committed SHA256 manifest supports later audit.

Failure analysis: actual sent prompts contain the intended observation. For b1_009 the top view is 000/000/001, but the first response's bottom layer is111/100/111, which already violates projection. b2_013 responses repeatedly copy the four-corner example. All nine projection checks fail; b3_084 query1 also floats a center voxel above an empty center. Thus this is not an HTTP failure, parsing outage or output truncation. Example imitation and difficulty following a long prompt are hypotheses; proving them requires an ablation, not retrospective assertions.

Quality gate failed. Formal test remains untouched. No model switch, prompt replacement, evaluator relaxation or simulated substitution has been made. Next proposed dev ablation: remove the unrelated example while preserving task constraints/output schema, comparing the same model/seeds/observations/budget. Report it separately; do not silently rename it the official baseline. Final formal protocol and the three methods' experiments remain pending this decision.


## Dev ablation: remove unrelated example

Same model, seeds, 3 dev observations and 9-call budget; method diagnostic_no_example:transform. Only remove the illustrative example and its following explanatory text. Real V=0, U=0.6666666666666666, R=0. Resource totals: {"calls": 9, "input_tokens": 4071, "output_tokens": 2700, "model_call_seconds": 359.9554256000047, "truncated_outputs": 3}. Deleting the example alone did not recover valid generation. Longer explanations and truncated responses appeared; this does not prove the example has no effect, and the small sample cannot characterize all model behavior. Both runs remain development-only.


# Formal Adapted Baseline result

585/585 real local Qwen calls completed. Model, sampling and data IDs were frozen using development data. A history implementation defect discovered in an aborted partial test run was repaired, rechecked on dev, and the complete 585-call run was restarted. No sampling hyperparameters were tuned on test, but test was not strictly unseen for this repair. Original official prompt remains available without --method. Adapted Baseline uses adapted_baseline:transform; teammate methods start from this same prompt.

Macro V=0.785185, U=0.216461, R=0.174486.
Calls=585; input tokens=178307; output tokens=28776; summed inference wall time=3275.129 seconds; truncated outputs=0. Cost=0 commercial API fees.

Full aggregate/sample SD, per-stratum results, task records and curves: figures/baseline/metrics.json. Raw output checksums: figures/baseline/raw-manifest.json. Full prompts, model responses and timings remain on SSD at HypoSpaceLocal/runs/adapted-formal-v4/raw. No outputs were replaced by simulated answers. Figures show all official scoring outcomes, including invalid and duplicate outputs.

Reproduce: python src/hypospace_runner.py --method adapted_baseline:transform --out <SSD>/runs/adapted-formal-v4
Export: python experiments/finalize_baseline.py (owner's default local path; otherwise use export_run.py and plot_results.py directly).

The adapted prompt improves task readability but is not a claimed novel algorithm. Small dev/test samples and prompt-based generation limit generalization. Development Original Baseline metrics and formal Adapted metrics use different observation/budget settings and must not be interpreted as a controlled test-set improvement estimate. The matched dev comparisons are in dev-study.json.

## 2026-11-26 Formal coverage-guided result

585/585 real local Qwen calls on `jcj129321/coverage-guided`, same model, seeds, observations and per-task budget as the frozen Adapted Baseline. The method appends a dimension-level search report after the baseline prompt: coverage k/n plus the heights actually used at each occupied cell. It never states an undiscovered structure, so the generator still has to construct the proposal itself.

Macro V=0.7786, U=0.2527, R=0.2189 vs frozen baseline V=0.7852, U=0.2165, R=0.1745.

Paired per (seed, observation), 45 pairs: Validity -0.66pp (95% CI [-4.64, +3.33], p=0.741), Uniqueness +3.62pp ([-0.29, +7.53], p=0.069), Recovery +4.44pp ([+0.14, +8.74], p=0.043). The preregistered threshold was Recovery >= +5pp, so this is reported as not met rather than re-framed after the fact.

By stratum: L1 R 37.78 -> 48.89, L2 10.37 -> 11.85, L3 4.20 -> 4.94. L2 Validity fell 60.00 -> 50.37 and that drop is not yet attributed by an ablation. At the end of every L3 task 89% of occupied cells had still never changed height (L2 80%, L1 53%), so the directive is largely ignored once the history is long.

Calls=585; input tokens=223990; output tokens=26383; summed inference wall time=1959.782 seconds; truncated outputs=0. Cost=0 commercial API fees.

Full aggregate/sample SD, per-stratum results, task records and curves: figures/cg/metrics.json. Raw output checksums: figures/cg/raw-manifest.json. Full prompts, responses and timings remain on SSD at HypoSpaceLocal/runs/cg-test-v1/raw. experiments/validate_coverage.py replays every raw response through the pinned official parser and reproduces each per-task score exactly.

Reproduce: python src/hypospace_runner.py --method coverage_guided:transform --out <SSD>/runs/cg-test-v1
Audit: python experiments/validate_coverage.py <SSD>/runs/cg-test-v1
Compare: python src/compare_runs.py docs/figures/baseline/metrics.json <SSD>/runs/cg-test-v1/summary.json --out docs/cg-comparison.json

Not done: dev ablation of the two components (`transform_stats_only` / `transform_cells_only`) and cross-machine calibration of the baseline. The frozen baseline was produced on a different host (Python 3.12.4) while this run used Python 3.12.10; compare_runs matches config, model fingerprint, split and dataset digest but not hardware.
