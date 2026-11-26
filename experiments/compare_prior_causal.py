"""Retest the frozen parent-set policy on the eight previously inspected main-test cases."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean

from run_parent_strata import ROOT, Dataset, LocalModel, digest, run_cell, save, score_prefix
from causal_benchmark import MODEL, SAMPLING, SYSTEM
from summarize_causal import verify_cells

CONTROLS = ("official", "edge_count", "reachability", "feedback", "structural_cycle", "adaptive")
BUDGET = 16


def read(path):
    return json.loads(path.read_text())


def audit_calls(folder, dataset, row):
    case, seed, method = row["case_id"], row["seed"], row["method"]
    base_seed = int(hashlib.sha256(case.encode()).hexdigest()[:8], 16) + seed
    outputs = []
    tokens = 0
    for step in range(BUDGET):
        step_seed = (base_seed + step) % 2147483647
        record = read(folder / "raw" / case / str(seed) / method / f"{step:03}.json")
        data = record["data"]
        request = data["request"]
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": data["prompt"]}]
        if (record["data_sha256"] != digest(data)
                or record["request_id"] != digest([data["prompt"], step_seed, method, 0])
                or data["seed"] != step_seed or request["options"] != {**SAMPLING, "seed": step_seed}
                or request["model"] != MODEL or data["resolved_model"] != MODEL or request["messages"] != messages):
            raise ValueError(f"Raw request differs from frozen model, sampling, or seed for {case}/{seed}/{method}/{step}")
        tokens += data["input_tokens"] + data["output_tokens"]
        outputs.append(data["response"])
    if score_prefix(dataset, dataset.cases[case], outputs) != row["prefixes"][str(BUDGET)]:
        raise ValueError(f"Official R/V/U replay differs for {case}/{seed}/{method}")
    if tokens != row["input_tokens"] + row["output_tokens"]:
        raise ValueError(f"Token count differs for {case}/{seed}/{method}")


def validate_history(old_folder, parent_identity, dataset):
    old = read(old_folder / "summary.json")
    p, identity = old["protocol"], old["identity"]
    if (read(old_folder / "identity.json") != identity or identity["model"] != parent_identity["model"]
            or identity["upstream"] != parent_identity["upstream"] or identity["upstream"] != dataset.provenance
            or identity["data"] != parent_identity["dataset"] or identity["data"] != digest(dataset.cases)
            or identity["protocol"] != digest(p) or p != read(ROOT / "experiments/causal-main.json")
            or p["budget"] != BUDGET or len(p["test"]) != 8 or p["test_seeds"] != [17, 42]
            or identity["split"] != "test" or old["split"] != "test"):
        raise ValueError("Historical identity, reference model, dataset, or protocol differs")
    for name, expected in parent_identity["code"].items():
        path = ROOT / ("experiments" if name.startswith("run_") else "src") / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source no longer matches frozen parent-strata experiment: {name}")
    verify_cells(old["rows"], p, "test")
    selected = [r for r in old["rows"] if r["method"] in CONTROLS]
    for row in selected:
        audit_calls(old_folder, dataset, row)
    return old, selected


def report(rows, old, reference):
    p = old["protocol"]
    results = {}
    for name in (*CONTROLS, "parent_set"):
        group = [r for r in rows if r["method"] == name]
        results[name] = {
            "calls": sum(r["calls"] for r in group),
            "tokens": sum(r["input_tokens"] + r["output_tokens"] for r in group),
            "macro": {key: mean(r[key] for r in group) for key in ("R", "V", "U")},
            "per_case_R": {case: mean(r["R"] for r in group if r["case_id"] == case) for case in p["test"]},
        }
    return {
        "study": "Retrospective matched retest on previously studied cases, separate from the new held-out study.",
        "case_ids": p["test"], "seeds": p["test_seeds"], "budget": BUDGET, "methods": results,
        "new_calls": results["parent_set"]["calls"],
        "delta_R_vs_prior": {name: results["parent_set"]["macro"]["R"] - results[name]["macro"]["R"]
                             for name in CONTROLS},
        "old_summary_sha256": digest(old), "prior_commit": old["identity"]["commit"],
        "generation_commit": reference["commit"], "model_digest": reference["model"]["digest"],
        "upstream_commit": reference["upstream"]["upstream_commit"], "dataset_digest": reference["dataset"],
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument("--replay", action="store_true")
    mode.add_argument("--check-history", action="store_true", help="Audit existing local records without model calls.")
    cli.add_argument("--prior", type=Path, default=ROOT / "runs/main-test")
    cli.add_argument("--reference", type=Path, default=ROOT / "runs/parent-dev/identity.json")
    cli.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    cli.add_argument("--out", type=Path, default=ROOT / "runs/parent-prior")
    cli.add_argument("--report", type=Path, default=ROOT / "docs/parent-strata-prior.json")
    args = cli.parse_args()
    reference = read(args.reference)
    dataset = Dataset(args.upstream)
    old, controls = validate_history(args.prior, reference, dataset)
    if args.check_history:
        print(f"Audited {len(controls) * BUDGET} historical responses.")
        return
    p = old["protocol"]
    model = None if args.replay else LocalModel()
    if model is not None and model.fingerprint() != reference["model"]:
        raise ValueError("Live model identity differs from historical experiment")
    identity = {"prior": digest(old), "reference": reference, "sampling": SAMPLING}
    path = args.out / "identity.json"
    if path.exists() or args.replay:
        if read(path) != identity:
            raise ValueError("Prior-retest identity differs")
    else:
        save(path, identity)
    rows = list(controls)
    for case in p["test"]:
        for seed in p["test_seeds"]:
            row = run_cell(dataset, model, dataset.cases[case], "parent_set", seed, BUDGET, args.out, args.replay)
            audit_calls(args.out, dataset, row)
            rows.append(row)
            print(case, seed, "R", round(row["R"], 4), flush=True)
    result = report(rows, old, reference)
    if args.replay:
        if read(args.report) != result:
            raise ValueError("Replayed prior-study report differs from the saved report")
        print("Verified prior-study report against all selected raw records.")
    else:
        save(args.report, result)


if __name__ == "__main__":
    main()
