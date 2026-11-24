# 3D baseline protocol v1

## Status

The official evaluator pipeline has completed 585 offline uniform-height control proposals. These are NOT LLM measurements. Real LLM baseline execution is pending the owner's model/provider and spending limit. Do not label the offline figures as LLM baseline results, and do not start final comparison runs until the model is frozen and the real baseline is complete.

The course Part 2 asks for a novel ML method improving LLM performance on HypoSpace, a public repository, and a 10-minute group video with every member speaking. This small 3D experiment is a course protocol, not a reproduction of the paper's full model/domain sweep.

## Frozen shared settings

Source of truth: `experiments/protocol.json` and `experiments/manifest.json`.
Official revision: `c69e9318577b34b5b896996571aefd4ba6053f58` from https://github.com/CTT-Pavilion/_HypoSpace.

- Domain: gravity-supported 3D reconstruction; 3x3 grid, maximum height 3.
- Occupied top-view cells: 1, 2, 3. Exactly 3, 9, 27 admissible structures respectively.
- Generate all 129 observations using the official generator; fixed disjoint split: 2 dev and 5 test observations per stratum. IDs and canonical JSON SHA256 committed in manifest. No solution sets are sent to a model or method hook.
- Split seed 33550336; repeat labels 17, 42, 2026. API does not accept these seeds: repeats are independent calls, NOT guaranteed deterministic LLM sampling. Offline control seeds are reproducible.
- Query count per task = |H| x 1.0; one proposal per call; no parser retry, no repair/replacement calls. 585 test calls per method; 234 dev calls per full dev run.
- Temperature 0.7, max output tokens 512, sequential calls, timeout 120 seconds, no automatic HTTP retries. HTTP failures stop execution; successful requests are cached for resumption. Parse failures consume one call and remain in the denominator.
- Provider adapter currently supports Anthropic-compatible Messages only. Model is unresolved, read from explicit config or ANTHROPIC_MODEL. Freeze an exact model ID in shared config before team experiments. Record returned model ID in each raw record; aliases may change.
- API call budget is not a dollar budget. Cost is null because proxy pricing is unknown. Get model/prices/budget from the owner before the first API request. `--allow-api-calls` is an explicit upper count gate, not a money cap.

## Baseline and metrics

Use the official `Benchmark3D.evaluate_single_observation_set` unmodified, its prompt, parser, normalization, hash and validator. The official baseline already includes ALL prior parsed distinct structures in the next prompt (the local last-10 variable is unused upstream). All methods inherit this unless an explicit ablation says otherwise.

V = valid proposals / requested proposals. U = distinct parsed proposals / requested proposals, including invalid distinct proposals. R = distinct valid recovered ground-truth hashes / enumerated ground-truth hashes. Parse failures contribute zero to the numerator. Trailing all-zero layers normalize away. Aggregate = macro average over 15 observations x 3 repeats, also reported separately by occupied-cell count. Standard deviation is descriptive across 45 task-repeat records, NOT a confidence interval over independent datasets. Use paired per-observation differences when analyzing future methods.

Known official evaluator limitation: it does not enforce maximum height in validity, and its parser pads irregular rows. Keep official metrics for comparability; `strict_valid_count` adds a height-bound diagnostic on parsed structures (not a strict raw-output grammar check). Do not silently patch the official evaluator for one method. It is possible to have official V=1 with R<1 because out-of-space structures are counted valid. Ground truth membership controls R.

At Q=|H| and when every valid structure belongs to the ground truth, U and R can coincide. Curves over k=1..Q and per-stratum results are needed to understand coverage. This toy 3D setting also admits exact non-ML enumeration; beating an LLM here alone does not establish scientific novelty or generalization. Use it as a controlled initial experiment and discuss this limitation in the video.

## Files and commands

From the repository root (Python 3.11 recommended):

```sh
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -r requirements.txt
python experiments/bootstrap.py
python src/hypospace_runner.py --prepare
python -m unittest discover -s tests -v
python src/hypospace_runner.py --mode offline --out runs/offline
python src/plot_results.py runs/offline/summary.json --out docs/figures/offline
```

After freezing the model, regenerate the manifest with `--prepare` and commit both configuration and manifest. Set credentials only via environment variables. Supported names: ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN; optional ANTHROPIC_BASE_URL (host root, without /v1/messages). Do not commit secrets or gateway URLs. With approved budget:

```sh
python src/hypospace_runner.py --mode llm --out runs/baseline --allow-api-calls 585
python src/plot_results.py runs/baseline/summary.json --out docs/figures/baseline
```

For development use `--split dev --out runs/baseline-dev --allow-api-calls 234`. Do not tune on test observations. Resume the exact command/directory; identity and prompt hashes reject changed configurations or changed method source. To rerun independently choose a new directory. Do not delete caches to hide unsuccessful attempts.

## Output contract

`identity.json`: resolved model, complete configuration, upstream revision, method name/source hash, dataset hash and split.
`raw/<seed>/<observation_id>/<query_index>.json`: prompt, response, request SHA256, usage, elapsed seconds, returned model. Ignored by Git; retain privately for audit.
`partial.json`: completed observation records for failure recovery.
`summary.json`: schema_version=1; identity, planned/completed calls, Python/platform, cost_usd=null, aggregate and by_blocks means/sample SD, official per-task results and prefix curves. Official names: valid_rate=V, novelty_rate=U, recovery_rate=R. Each task has IDs, seed, blocks, counts, parse_success_rate, token_usage, latency_s, strict_valid_count and structures. Curves are computed by replaying saved outputs: no extra API calls.

Commit only sanitized small summaries and figures under docs, never raw responses, credentials, full datasets or .cache. Include exact run command and source commit in experiment log. Count input/output tokens as well as calls: methods with longer prompts can have greater monetary/compute costs even at equal call budget.

## Three teammate interfaces

Implement a Python module under src with function `transform(prompt: str, context: dict) -> str`. Context has only observation, query_index, history (prior response texts). Launch `--method my_method:transform` with a separate output directory. The hook only changes prompts; it must return one string and must not make extra model calls, read solutions/test results, or perform hidden search/repair. Methods needing additional calls or candidate selection require a new shared budget protocol and a rerun of ALL methods.

Suggested, unvalidated directions (not claims of novelty): A stratify by requested column-height patterns; B adapt next target to coverage descriptors extracted from prior responses; C diversify spatial traversal/order or representation while requiring the same final layer output. Plain history de-duplication is already baseline. Each person must explain their method, run a dev ablation, freeze settings, then run test once and report failures and resource usage. For a genuinely learned method, train/tune only on dev; do not present a prompt heuristic as a trained ML model.
