"""Generate frozen, observation-only strata or replay their raw local model calls."""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from run_causal import ROOT, digest, obtain, save, score_prefix
from causal_benchmark import Dataset, LocalModel
from causal_prompts import _reachability
from parent_strata import parent_plan

PROTOCOL = ROOT / "experiments/parent-strata.json"


def fixed_conditions(public, method, seed, budget):
    if method == "parent_set":
        return parent_plan(public, seed, budget)
    if method == "edge_count":
        # Reuse the lower bound and ascending rotation of the main-branch comparator.
        lower = max(sum(obs["effects"].values()) for obs in public["observations"])
        counts = range(lower, public["max_edges"] + 1)
        return [dict(count=counts[i % len(counts)],
                     prompt=f"Use exactly {counts[i % len(counts)]} directed edges.")
                for i in range(budget)]
    if method in ("official", "unstratified"):
        return [{} for _ in range(budget)]
    raise ValueError(f"Unknown method {method}")


def run_cell(dataset, model, row, method, seed, budget, out, replay):
    oid = row["observation_set_id"]
    public = {key: row[key] for key in ("nodes", "max_edges", "observations")}
    start = time.perf_counter()
    conditions = fixed_conditions(public, method, seed, budget)
    base, format_line = _reachability(public, []).rsplit("\n", 1)
    prompts = ["\n".join(filter(None, [base, c.get("prompt"), format_line])) for c in conditions]
    prep = (time.perf_counter() - start) / budget
    base_seed = int(hashlib.sha256(oid.encode()).hexdigest()[:8], 16) + seed
    prior, records = [], []
    hits = 0 if method in ("parent_set", "edge_count") else None
    for index, (condition, prompt) in enumerate(zip(conditions, prompts, strict=True)):
        if method == "official":
            prompt = dataset.bench.create_prompt(public["observations"], prior)
        step_seed = (base_seed + index) % 2147483647
        path = out / "raw" / oid / str(seed) / method / f"{index:03}.json"
        data = obtain(path, model, prompt, step_seed, method, 0, replay, prep)
        records.append(data)
        graph = dataset.bench.parse_llm_response(data["response"])
        if graph is None:
            continue
        if method == "official":
            prior.append(graph)
        elif method == "parent_set":
            parents = {source for source, target in graph.edges if target == condition["node"]}
            hits += int(parents == set(condition["parents"]))
        elif method == "edge_count":
            hits += int(len(graph.edges) == condition["count"])
    outputs = [data["response"] for data in records]
    scores = {str(k): score_prefix(dataset, row, outputs[:k]) for k in (4, 8, budget) if k <= budget}
    return dict(case_id=oid, seed=seed, method=method, calls=budget,
                solution_count=row["n_compatible_graphs"], assignment_hits=hits,
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
    args = cli.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    out = args.out or ROOT / "runs" / ("parent-" + args.split)
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
                cell = run_cell(dataset, model, dataset.cases[oid], method, seed, protocol["budget"], out, args.replay)
                rows.append(cell)
                print(oid, seed, method, f"R={cell['R']:.4f}", flush=True)
    summary = dict(protocol=protocol, rows=rows, identity=identity, split=args.split)
    if args.replay:
        if json.loads((out / "summary.json").read_text()) != summary:
            raise ValueError("Official replay differs from recorded summary")
        print(f"Verified {len(rows)} cells against raw responses")
    else:
        save(out / "summary.json", summary)


if __name__ == "__main__":
    main()
