"""Run or replay the matched boolean gene-interaction experiment.

Four methods share the same cases, seeds, budget and model:
  official          - upstream prompt loop with accumulated hypothesis history
  completion        - verbal completion strata, free-form expression
  skeleton          - one-hole skeleton fixed in the prompt, stratum-enforced acceptance
  skeleton_valid    - skeleton plus deterministic validity rescue (final method)
All model calls use the local Ollama model; scoring replays the official
evaluator on the assembled outputs.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from run_causal import ROOT, digest, obtain, save
from causal_benchmark import LocalModel
from boolean_benchmark import COLLECTION, Dataset, load_official
from boolean_prompts import completion_prompt, skeleton_prompt
from boolean_space import assemble, completion_plan, skeleton_plan

PROTOCOL = ROOT / "experiments/boolean-skeleton.json"
UPSTREAM = ROOT / ".cache/hypospace"
METHOD_VARIANTS = {"completion", "skeleton", "skeleton_valid"}


def output_line(text):
    return f"Expression: {text}" if text else ""


def score_prefix(dataset, case, outputs):
    scored = dataset.score(case, outputs)
    return dict(V=scored["valid_rate"], U=scored["novelty_rate"], R=scored["recovery_rate"],
                valid=scored["n_valid"], parsed=scored["parse_success_rate"],
                recovered=scored["n_recovered_gts"])


def run_cell(dataset, model, case, method, seed, budget, out, replay):
    oid = case["observation_set_id"]
    public = {key: case[key] for key in ("observations", "variables", "operators", "max_depth")}
    _, dataset_module = load_official(dataset._upstream)
    base_seed = int(hashlib.sha256(oid.encode()).hexdigest()[:8], 16) + seed
    records, outputs = [], []
    if method == "official":
        observations = [dataset_module.BooleanObservation(obs["inputs"], obs["output"])
                        for obs in case["observations"]]
        prior = []
        for index in range(budget):
            step_seed = (base_seed + index) % 2147483647
            start = time.perf_counter()
            prompt = dataset.bench.create_prompt(observations, prior)
            path = out / "raw" / oid / str(seed) / method / f"{index:03}.json"
            data = obtain(path, model, prompt, step_seed, method, 0, replay,
                          time.perf_counter() - start)
            records.append(data)
            parsed = dataset.bench.parse_llm_response(data["response"])
            if parsed:
                prior.append(parsed)
            outputs.append(data["response"])
    else:
        if method == "completion":
            conditions = completion_plan(dataset._upstream, public, seed, budget)
            prompts = [completion_prompt(public, c) for c in conditions]
        else:
            conditions = skeleton_plan(dataset._upstream, public, seed, budget)
            prompts = [skeleton_prompt(public, c) for c in conditions]
        for index, (condition, prompt) in enumerate(zip(conditions, prompts, strict=True)):
            step_seed = (base_seed + index) % 2147483647
            path = out / "raw" / oid / str(seed) / method / f"{index:03}.json"
            data = obtain(path, model, prompt, step_seed, method, 0, replay, 0.0)
            records.append(data)
            final = assemble(dataset, condition, data["response"], method)
            outputs.append(output_line(final))
    prefixes = {str(k): score_prefix(dataset, case, outputs[:k]) for k in (4, 8, 13, budget)}
    return dict(case_id=oid, seed=seed, method=method, calls=budget,
                solution_count=case["n_compatible_expressions"],
                input_tokens=sum(d["input_tokens"] for d in records),
                output_tokens=sum(d["output_tokens"] for d in records),
                seconds=sum(d["seconds"] for d in records),
                truncated=sum(d["done_reason"] == "length" for d in records),
                prefixes=prefixes, **prefixes[str(budget)])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--split", choices=["dev", "test"], required=True)
    cli.add_argument("--replay", action="store_true")
    cli.add_argument("--upstream", type=Path, default=UPSTREAM)
    cli.add_argument("--out", type=Path)
    cli.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = cli.parse_args()
    protocol = json.loads(args.protocol.read_text())
    out = args.out or ROOT / "runs" / ("boolean-" + args.split)
    dataset = Dataset(args.upstream, ROOT / ".cache" / COLLECTION)
    model = None if args.replay else LocalModel()
    identity_file = out / "identity.json"
    existing = json.loads(identity_file.read_text()) if identity_file.exists() else None
    if args.replay and existing is None:
        raise FileNotFoundError(identity_file)
    files = [Path(__file__), ROOT / "experiments/run_causal.py",
             *(ROOT / "src" / name for name in ("causal_benchmark.py", "boolean_benchmark.py",
                                                "boolean_prompts.py", "boolean_space.py"))]
    collection_bytes = dataset.collection_path.read_bytes()
    identity = dict(model=existing["model"] if args.replay else model.fingerprint(),
                    upstream=dataset.provenance,
                    collection_sha256=hashlib.sha256(collection_bytes).hexdigest(),
                    dataset=digest(dataset.cases), protocol=digest(protocol),
                    code={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                    split=args.split)
    if existing:
        if any(existing[k] != v for k, v in identity.items()):
            raise ValueError("Frozen run identity mismatch")
        identity = existing
    else:
        identity["commit"] = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        save(identity_file, identity)
    rows = []
    for oid in protocol[args.split]:
        for seed in protocol[args.split + "_seeds"]:
            for method in protocol["methods"]:
                cell = run_cell(dataset, model, dataset.cases[oid], method, seed,
                                protocol["budget"], out, args.replay)
                rows.append(cell)
                print(oid, seed, method,
                      *[round(cell[k], 4) for k in ("V", "U", "R")], flush=True)
    summary = dict(protocol=protocol, rows=rows, identity=identity, split=args.split)
    if args.replay:
        if json.loads((out / "summary.json").read_text()) != summary:
            raise ValueError("Boolean replay differs from recorded summary")
        print(f"Verified {len(rows)} boolean cells against raw responses")
    else:
        save(out / "summary.json", summary)


if __name__ == "__main__":
    main()
