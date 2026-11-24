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
