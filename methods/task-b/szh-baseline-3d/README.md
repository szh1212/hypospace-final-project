# 3D baselines — Task B

Original and adapted each preserve 585 real calls. Shared transport, evaluator and runner are in src/; frozen model/protocol/split files are in experiments/. Original official prompts are reproduced by the pinned upstream Benchmark3D.create_prompt; exact issued prompts are also in original/reports/raw.jsonl.gz. The adapted prompt implementation is src/adapted_baseline.py, shared without duplicate copies.

- [Original results and raw archive](original/reports/metrics.json)
- [Adapted results and raw archive](adapted/reports/metrics.json)
- [Paired report](docs/paired-results.md)
- [Frozen protocol](experiments/protocol.json)

Run from the repository root: `python methods/task-b/szh-baseline-3d/original/run.py --out runs/original-new` or `python methods/task-b/szh-baseline-3d/adapted/run.py --out runs/adapted-new`. These commands launch inference only when explicitly invoked; integration uses only offline replay: `python experiments/audit_integration.py`.

Legacy src/ and experiments/ Python paths are small compatibility entry points executing these canonical implementations. Development records and figures are preserved under development/.
