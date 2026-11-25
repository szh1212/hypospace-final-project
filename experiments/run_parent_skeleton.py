"""Generate structurally enforced parent-set strata (skeleton cells only).

The four paired controls are the frozen parent-strata v1 cells under
runs/parent-{split}; this script never regenerates them. Skeleton cells use
the same seed schedule, sampling and budget so the five methods stay paired
by case and seed.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from run_causal import ROOT, digest, obtain, save, score_prefix
from causal_benchmark import Dataset, LocalModel
from causal_prompts import _reachability
from parent_strata import assemble, skeleton_plan

PROTOCOL = ROOT / "experiments/parent-skeleton.json"


def canonical(edges):
    return "Graph: " + ", ".join(f"{s}->{t}" for s, t in sorted(edges)) or "Graph: No edges"


def run_skeleton_cell(dataset, model, row, method, seed, budget, out, replay):
    variant = method.split("_", 1)[1]
    oid = row["observation_set_id"]
    public = {key: row[key] for key in ("nodes", "max_edges", "observations")}
    start = time.perf_counter()
    conditions = skeleton_plan(public, seed, budget, variant)
    base, format_line = _reachability(public, []).rsplit("\n", 1)
    prompts = ["\n".join(filter(None, [base, c.get("prompt"), format_line])) for c in conditions]
    prep = (time.perf_counter() - start) / budget
    base_seed = int(hashlib.sha256(oid.encode()).hexdigest()[:8], 16) + seed
    records, outputs, assembled = [], [], []
    for index, (condition, prompt) in enumerate(zip(conditions, prompts, strict=True)):
        step_seed = (base_seed + index) % 2147483647
        path = out / "raw" / oid / str(seed) / method / f"{index:03}.json"
        data = obtain(path, model, prompt, step_seed, method, 0, replay, prep)
        records.append(data)
        graph = dataset.bench.parse_llm_response(data["response"])
        final = assemble(condition, graph.edges if graph is not None else [])
        outputs.append(canonical(final))
        assembled.append(sorted(final))
    scores = {str(k): score_prefix(dataset, row, outputs[:k]) for k in (4, 8, budget) if k <= budget}
    return dict(case_id=oid, seed=seed, method=method, calls=budget,
                solution_count=row["n_compatible_graphs"], assembled=assembled,
                input_tokens=sum(d["input_tokens"] for d in records),
                output_tokens=sum(d["output_tokens"] for d in records),
                seconds=sum(d["seconds"] for d in records),
                truncated=sum(d["done_reason"] == "length" for d in records),
                prefixes=scores, **scores[str(budget)])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--split", choices=["dev", "test"], required=True)
    cli.add_argument("--replay", action="store_true")
    cli.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    cli.add_argument("--out", type=Path)
    cli.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = cli.parse_args()
    protocol = json.loads(args.protocol.read_text())
    out = args.out or ROOT / "runs" / ("skeleton-" + args.split)
    dataset = Dataset(args.upstream)
    model = None if args.replay else LocalModel()
    identity_file = out / "identity.json"
    existing = json.loads(identity_file.read_text()) if identity_file.exists() else None
    if args.replay and existing is None:
        raise FileNotFoundError(identity_file)
    files = [Path(__file__), ROOT / "experiments/run_causal.py",
             *(ROOT / "src" / name for name in ("causal_benchmark.py", "causal_prompts.py", "parent_strata.py"))]
    identity = dict(model=existing["model"] if args.replay else model.fingerprint(),
                    upstream=dataset.provenance, dataset=digest(dataset.cases), protocol=digest(protocol),
                    code={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    split=args.split)
    if existing:
        if any(existing[k] != v for k, v in identity.items()):
            raise ValueError("Frozen run identity mismatch")
        identity = existing
    else:
        identity["commit"] = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        save(identity_file, identity)
    rows = []
    for oid in protocol[args.split]:
        for seed in protocol[args.split + "_seeds"]:
            for method in protocol["methods"]:
                cell = run_skeleton_cell(dataset, model, dataset.cases[oid], method, seed,
                                         protocol["budget"], out, args.replay)
                rows.append(cell)
                print(oid, seed, method, f"R={cell['R']:.4f}", flush=True)
    summary = dict(protocol=protocol, rows=rows, identity=identity, split=args.split)
    if args.replay:
        if json.loads((out / "summary.json").read_text()) != summary:
            raise ValueError("Skeleton replay differs from recorded summary")
        print(f"Verified {len(rows)} skeleton cells against raw responses")
    else:
        save(out / "summary.json", summary)


if __name__ == "__main__":
    main()
