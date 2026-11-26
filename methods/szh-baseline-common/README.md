# Shared adapted baseline runner

This framework reuses methods/szh-baseline-3d-task-b/src/ollama_client.py unchanged and the pinned official parsers, validators, canonicalizers and evaluator. Prompts receive only metadata, observations and unique parsed prior responses. No solution references, filtering, repairs, enumeration, stratification or coverage feedback are used in generation. Reference enumeration occurs only in official data preparation and evaluation.

Install the repository requirements and sympy==1.13.3. Place the clean official repository at ../upstream-hypospace, pinned to c69e9318577b34b5b896996571aefd4ba6053f58.

```powershell
python methods/szh-baseline-common/prepare_data.py
python experiments/run_domain.py --prepare
python experiments/run_domain.py --domain causal --stage smoke
python experiments/run_domain.py --domain genetic --stage smoke
python experiments/run_domain.py --stage freeze
python experiments/run_domain.py --domain causal --stage test
python experiments/run_domain.py --domain genetic --stage test
python experiments/audit_all_domains.py --domain causal
python experiments/audit_all_domains.py --domain genetic
```

Resume with the identical command. Every completed request is saved atomically and checked against reconstructed history and seed. Incomplete transport calls abort without fabricating a response. Console output and runs/all-domains/<domain>/<stage>/progress.json report completed/total calls, percentage, case, seed and invalid-output count. Model version, digest and quantization are checked before inference. Audit requires every raw request and score to match; it makes no model calls.

Protocol remains DRAFT until real development smoke tests pass and freeze.json is written. Raw requests/responses remain under ignored runs/; tracked reports contain summaries, SHA256 manifests and a deterministic compressed raw.jsonl.gz archive after successful replay, following the published 3D archive format. Do not regenerate data/configuration over a frozen experiment. The reference-generator hash seed is fixed at zero.

The unified causal subset uses five test and two dev observations per intervention-count stratum at four nodes, max four edges. It is a four-node study; paper levels at five/six nodes are not claimed. Boolean uses five shared test and two shared dev observation identities in each operator regime at depth two; operator regimes are the reported levels. Budget is the official number of compatible hypotheses. Causal aligned cases receive at least 16 calls, reusing the same records for prefixes 4,8,13,16; unified metrics use only the frozen unified subset and official budgets. All calls including extra alignment calls are disclosed.

Macro averages weight case-seed cells equally. Micro rates pool numerators and denominators, retaining separate seed cells; they do not merge seed outputs before deduplication. Across-seed standard deviation is computed from seed-level macro means with ddof=1. Parsed unique history includes parsed invalid outputs, consistent with the original adapted baseline; it is not an oracle feedback channel.

For a checkout that already contains freeze.json and the committed protocol, regenerate data only with prepare_data.py, verify the committed data hashes, then run test/audit. The --prepare and --stage freeze commands above describe initial development setup and must not overwrite a published frozen protocol. The teammate-aligned case IDs are stored explicitly in protocol.json; the inspected teammate source revision is recorded in docs/baseline-all-domains/audit.md.

Install shared dependencies from the repository root with `python -m pip install -r methods/szh-baseline-common/requirements.txt`. The published 3D per-seed means, sample standard deviations and micro rates are derived without new inference in docs/baseline-all-domains/published-3d-statistics.json.

To restore a published new-task archive in a fresh checkout (after installing dependencies and preparing official data), run `python experiments/restore_all_domains_archive.py --domain causal` and the corresponding `--domain genetic`, then run each `experiments/audit_all_domains.py --domain <domain>` command. This validates every archived byte against the tracked manifest and refuses to overwrite different records. The generation/replay identity preserves the original Windows source-path representation.

After both formal audits, run `python experiments/finalize_all_domains.py` and `python experiments/diagnose_all_domains.py` for the reported-method comparison, seed statistics and diagnostic breakdown. Published 3D replay uses `python experiments/audit_all_domains_3d.py` with the original ignored 3D data prepared by the existing runner; it performs zero inference calls.

The frozen runner retains its original in-memory summary comparison. Causal graph edges are tuples in memory and lists in JSON, so use experiments/audit_all_domains.py for final replay: it compares the complete summary in canonical JSON form with no metric tolerance or omitted fields. This wrapper leaves frozen generation/evaluation sources unchanged. After audits, run `python experiments/run_frozen_utility.py plot` and `python experiments/run_frozen_utility.py report` before the final comparison/diagnostic scripts.

Repeat seeds are 17/42/2026. Individual request seeds preserve the 3D runner's schedule: `(repeat_seed + int(SHA256(observation_id)[:8],16) + query_index) % 2147483647`. Every actual seed is included in the archived request.

Generate the constant-cohort recovery figure with `python experiments/plot_all_domains_supplement.py`. It uses saved prefixes only, without new model calls.

The repository attributes preserve exact bytes for the frozen common Python sources, preventing Git line-ending conversion from invalidating the pre-inference SHA256 hashes. Staged source bytes were independently checked against freeze.json before publication.

Integration keeps the published frozen sources and identities byte-exact. experiments/integration_paths.py translates historical artifact locations at runtime; experiments/run_domain.py is the current inference entry. Frozen execute.py is retained as provenance; use the individually listed commands for current execution. Historical filenames within archived result JSON are provenance, not mutable runtime paths.
