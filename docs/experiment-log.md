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

## Pending real baseline

Model/provider and API budget are unresolved. Real baseline V/U/R, latency, token totals and cost are not available. Once authorized, pin the exact model in protocol.json, regenerate/commit manifest, run the LLM command in baseline-protocol.md, export sanitized summaries and figures, and record the source commit, provider/model returned IDs and exact command here.
