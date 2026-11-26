"""Offline audit of a finished run: zero model calls, zero new budget.

Re-parses every recorded raw response with the pinned official parser and
re-derives the outcome categories the paper reports:

    parse failure | invalid structure | valid duplicate | new valid

It then checks the bookkeeping that coverage_guided.transform relies on:

  * distinct valid structures per task must equal the evaluator's own
    ``n_recovered_gts``;
  * recounting valid/total and distinct/ground-truth must reproduce the
    summary's per-task ``valid_rate`` and ``recovery_rate``.

If both hold, the height-vector accounting in the hook agrees with the
official scorer, and the coverage report the model sees is truthful.

Usage:
    python methods/task-b/jcj-coverage-guided/experiments/validate_coverage.py <run-dir> [--json]

<run-dir> is a directory produced by methods/task-b/szh-baseline-3d/src/hypospace_runner.py in --mode llm.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".git").exists())
sys.path.insert(0, str(ROOT / "src"))

from hypospace_runner import upstream  # noqa: E402
from coverage_guided import heights_of  # noqa: E402

TOL = 1e-9


def observations_by_id():
    """Observation strings only. Ground truth is deliberately not read."""
    data = json.loads((ROOT / "data" / "3d.json").read_text(encoding="utf-8"))
    return {o["observation_id"]: o["observation"] for o in data["observation_sets"]}


def audit(run_dir):
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    if summary["identity"]["mode"] != "llm":
        raise SystemExit("offline runs carry synthetic answers; audit a real --mode llm run only")

    parser = object.__new__(upstream()[0].Benchmark3D)
    obs_by_id = observations_by_id()

    categories = Counter()
    per_level = defaultdict(list)
    per_task = []
    problems = []

    for task in summary["results"]:
        oid = task["observation_set_id"]
        seed = task["seed"]
        observation = obs_by_id[oid]
        paths = sorted((run_dir / "raw" / str(seed) / oid).glob("*.json"))
        if len(paths) != task["n_queries"]:
            raise SystemExit(f"{oid}/{seed}: {len(paths)} raw records but n_queries={task['n_queries']}")

        seen = set()
        valid = 0
        never_varied = 0
        for path in paths:
            text = json.loads(path.read_text(encoding="utf-8"))["response"]
            heights = heights_of(text, observation, parser)
            if heights is None:
                parsed = parser.parse_llm_response(text)
                categories["parse failure" if parsed is None else "invalid structure"] += 1
                continue
            valid += 1
            if heights in seen:
                categories["valid duplicate"] += 1
            else:
                seen.add(heights)
                categories["new valid"] += 1

        cells = [i for i, bit in enumerate(observation) if bit == "1"]
        used = {i: {h[i] for h in seen} for i in cells}
        never_varied = sum(1 for i in cells if len(used[i]) <= 1)

        valid_rate = valid / task["n_queries"]
        recovery_rate = len(seen) / task["n_ground_truths"] if task["n_ground_truths"] else 0.0

        if len(seen) != task["n_recovered_gts"]:
            problems.append(
                f"{oid}/{seed}: recount found {len(seen)} distinct valid structures, "
                f"evaluator reported n_recovered_gts={task['n_recovered_gts']}"
            )
        if abs(valid_rate - task["valid_rate"]) > TOL:
            problems.append(f"{oid}/{seed}: valid_rate {valid_rate:.6f} vs {task['valid_rate']:.6f}")
        if abs(recovery_rate - task["recovery_rate"]) > TOL:
            problems.append(
                f"{oid}/{seed}: recovery_rate {recovery_rate:.6f} vs {task['recovery_rate']:.6f}"
            )

        per_level[task["blocks"]].append((recovery_rate, never_varied / len(cells)))
        per_task.append(
            {
                "seed": seed,
                "observation_set_id": oid,
                "blocks": task["blocks"],
                "calls": task["n_queries"],
                "valid": valid,
                "distinct_valid": len(seen),
                "recovery_rate": recovery_rate,
                "never_varied_cells": never_varied,
            }
        )

    return {
        "run": str(run_dir),
        "method": summary["identity"]["method"],
        "plan": "calls counted from raw records, not from the summary",
        "total_calls": sum(t["n_queries"] for t in summary["results"]),
        "categories": dict(categories),
        "by_level": {
            str(level): {
                "tasks": len(rows),
                "mean_recovery": sum(r for r, _ in rows) / len(rows),
                "mean_never_varied_fraction": sum(f for _, f in rows) / len(rows),
            }
            for level, rows in sorted(per_level.items())
        },
        "problems": problems,
        "tasks": per_task,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    report = audit(args.run)
    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"run      {report['run']}")
    print(f"method   {report['method']}")
    print(f"calls    {report['total_calls']}")
    print("\noutcome categories (all proposals, failures included)")
    for key in ("parse failure", "invalid structure", "valid duplicate", "new valid"):
        print(f"  {key:<18}{report['categories'].get(key, 0)}")
    print("\nper level")
    for level, row in report["by_level"].items():
        print(
            f"  level {level}: recovery {row['mean_recovery']:.4f}   "
            f"cells never varied {row['mean_never_varied_fraction']:.2f}"
        )
    if report["problems"]:
        print("\nMISMATCH - the hook's accounting is not the evaluator's:")
        for line in report["problems"][:20]:
            print(f"  {line}")
        raise SystemExit(1)
    print("\nOK: the hook's height-vector accounting reproduces every per-task score.")


if __name__ == "__main__":
    main()
