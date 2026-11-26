# All-domain baseline audit (in progress)

Status: COMPLETE for both new formal LLM experiments and offline replay. A: 2,019 calls; C: 270 calls. GitHub publication follows the validated artifacts.

## Verified provenance

- Team base: aaf9438cbbbf46ba1875a9e4d2b11ca629fb581f.
- Official source: c69e9318577b34b5b896996571aefd4ba6053f58 (local sibling upstream-hypospace).
- LWT source inspected: 47c9500c22e4c35a931a76544677fb31baef74a3.
- Existing 3D configuration: methods/szh-baseline-3d-task-b/experiments/protocol.json; model lock: methods/szh-baseline-3d-task-b/experiments/model-lock.json.
- Sampling matches the requested settings, plus repeat_penalty=1, num_thread=4, num_gpu=0 and Ollama 0.40.18. No sampling changes have been authorized or made.
- Existing 3D results remain unchanged. The available runs/offline* identity files describe uniform-height-control, not LLM runs. The published methods/szh-baseline-3d-task-b/adapted/reports/raw.jsonl.gz archive was located using commit 101a6c3; all 585 requests, hashes and official scores now replay successfully (historical-3d-replay.json).

## Official dataset preparation

Generated with the pinned official generators, seed 33550336; data remain ignored by Git. These are evaluator reference sets, never model-generated results or prompt inputs.

| Dataset | Settings | Hypothesis space | Observation sets |
| --- | --- | ---: | ---: |
| Causal | Four labeled nodes, at most four edges, one or two interventions | 411 | 236 |
| Boolean basic | x,y; AND,OR; depth 2 | 10 | 35 |
| Boolean extended | x,y; AND,OR,NOT; depth 2 | 34 | 78 |
| Boolean full | x,y; AND,OR,NOT,NOR; depth 2 | 65 | 80 |

These settings were frozen after independent development smoke testing. The paper's causal difficulty levels use 4/5/6 nodes; intervention counts must not be relabeled as those difficulty levels. The four-node dataset supports the teammate-aligned comparison. Final selection and budget need to be frozen after independent development smoke tests.

## Scoring and comparison constraints

Official Uniqueness is unique in-space parsed hypotheses divided by all attempts. Boolean Recovery uses mechanistic structural keys, not truth-table equivalence. Invalid outputs must remain in denominators. Parsing, scoring and canonicalization must not become generation repair or oracle selection.

LWT's final protocol uses 13 test cases and budget 16; report prefixes 4,8,13,16 from the same records. Its source uses num_predict=256 and num_gpu=99, whereas the baseline locks 512 and CPU. Same-case/same-call-budget results must disclose this difference. Cross-domain Recovery is descriptive, not a fair algorithm comparison. Teammate metrics are cited from its formal report by user instruction; label Historical Replay Not Verified. This does not block new experiments.

## Environment

Installed the repository's pinned CPU-only Ollama 0.40.18 portable package under C:/Users/CEG/HypoSpaceLocal/ollama, verified the local server reports 0.40.18. Exact Qwen model download has been attempted; digest and template verification passed against the original 3D model lock. Dependencies were installed in an isolated virtual environment on D:; no weights or environments are tracked.

## Outstanding work

Prompt adaptation, smoke tests, frozen formal inference, complete raw replay, compressed archives, English figures, statistical report and twelve regression tests are complete. The independent branch and PR provide the reviewable publication.

## Development and freeze

Both tasks completed two independent-development smoke passes before formal testing. First pass: causal 1/12 valid, Boolean 0/18 valid. The Boolean prompt was revised only on development observations: replace dictionary-style observations with an explicit binary input/output table and describe only allowed operators. No candidate examples, enumeration, repair, filtering or oracle feedback was added. The unchanged causal prompt was rerun alongside the second Boolean pass to validate the final runner. Second pass: causal 1/12 valid, Boolean 12/18 valid. All 60 development calls and accounting are preserved in development-study.json and development-raw.jsonl.gz.

The final protocol and source hashes were frozen before the first formal call. Frozen source is under methods/szh-baseline-common/freeze.json. No formal-output-driven prompt tuning is permitted. Low validity is an experimental outcome, not a reason to discard a proposal.

The official Boolean evaluator delegates expression parsing to SymPy; some lowercase Python Boolean expressions can be interpreted in unexpected ways. Official V/U/R are preserved exactly; raw output strings remain available for diagnosis. No parser normalization or validity repair was added to generation.

## Diagnostic interpretation

Official causal parser rejection includes malformed text, unknown nodes, self loops, edge-limit violations and cycles; the aggregated parse-failure category therefore includes structural parser rejections. Parsed-invalid means the official parser accepted the proposal but observations were not satisfied (or, for Boolean, space/semantic validation failed). Valid duplicates are counted separately from invalid outputs. All diagnostics use the unmodified official parser and evaluator.

The unified Boolean test observations selected before inference each contain three input/output pairs, shared across the three operator regimes to keep development/test identities disjoint across regimes. The reported per-level comparison varies operator sets at fixed depth and observation count.

## Runtime disclosure

New experiment orchestration uses Python 3.11.7 and the repository-pinned NumPy/SciPy/requests versions, plus SymPy 1.13.3 for Boolean evaluation. The earlier local setup guide described Python 3.12. This host only supplied Python 3.11.7; no model/sampling parameter was changed. Compatibility was checked with all ten regression tests and the successful 585-call published 3D raw replay using the pinned official evaluator.

## Official Boolean reference/validator inconsistency

Post-hoc checks found that the official `_in_space` validator rejects 0/10 basic, 1/34 extended, and 31/65 full reference formula representatives generated by the pinned official generator at depth two. This includes the extended expression `NOT (x OR y)`, which the validator treats as requiring the NOR primitive even though NOT and OR are allowed. Other full-regime rejections involve depth and formula interpretation. See official-space-check.json for exact representatives. Rejection of a representative alone does not prove every alternative expression with that mechanistic key is unattainable.

All primary results retain the official reference denominators, parser and V/U/R evaluation unchanged. No reference answers were removed, rewritten or exposed during generation. This inconsistency limits interpretation of Boolean Recovery as exhaustive coverage of a strictly validator-accepted space; it must be disclosed alongside model failures. The new raw replay verifies consistency with the pinned implementation, not correctness of every upstream design choice.

## Replay serialization repair

The first causal replay reconstructed all 2,019 requests but the final Python-object comparison failed because upstream CausalGraph.to_dict retains edge tuples while saved JSON has edge lists. Generation, prompts, scores, configuration and source freeze remain unchanged. experiments/audit_all_domains.py compares the complete summary after canonical JSON serialization, preserving every field and exact numeric values. Two regression tests verify that tuple/list representations match and a changed validity count is rejected. This is an audit serialization repair, not test-driven prompt or algorithm tuning.
