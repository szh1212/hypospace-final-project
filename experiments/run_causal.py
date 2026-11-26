"""Run or replay the matched causal experiment. All model calls use local Ollama."""
import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from causal_benchmark import Dataset, LocalModel
from causal_prompts import prompt_for

ACTION_METHODS = {"action_llm", "action_uniform"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def obtain(path, model, prompt, seed, method, menu_size, replay, preparation_s):
    request_id = digest([prompt, seed, method, menu_size])
    if path.exists():
        record = json.loads(path.read_text())
        if record["request_id"] != request_id or digest(record["data"]) != record["data_sha256"]:
            raise ValueError(f"Record failed integrity check: {path}")
        return record["data"]
    if replay:
        raise FileNotFoundError(path)
    if method == "action_uniform":
        choice = random.Random(seed).randrange(menu_size) + 1 if menu_size else 0
        data = dict(response=f"Choice: {choice}", input_tokens=0, output_tokens=0, seconds=0.0,
                    done_reason="symbolic", prompt=prompt, seed=seed)
    else:
        data = model.generate(prompt, seed)
        data.update(prompt=prompt, seed=seed)
    data["preparation_s"] = preparation_s
    save(path, dict(request_id=request_id, data_sha256=digest(data), data=data))
    return data


def score_prefix(dataset, row, outputs):
    scored = dataset.score(row, outputs)
    return dict(V=scored["valid_rate"], U=scored["novelty_rate"], R=scored["recovery_rate"],
                valid=scored["n_valid"], parsed=scored["parse_success_count"],
                recovered=scored["n_recovered_gts"])


def run_cell(dataset, model, row, method, seed, budget, folder, replay):
    from causal_actions import action_menu, action_prompt, decode_choice
    oid = row["observation_set_id"]
    public = {key: row[key] for key in ("nodes", "observations", "max_edges")}
    prior, previous, outputs, raw, trace = [], [], [], [], []
    base_seed = int(hashlib.sha256(oid.encode()).hexdigest()[:8], 16) + seed
    for index in range(budget):
        step_seed = (base_seed + index) % 2147483647
        start = time.perf_counter()
        if method in ACTION_METHODS:
            menu = action_menu(public, previous, index, seed)
            prompt = action_prompt(public, menu)
        else:
            menu = []
            original = dataset.bench.create_prompt(public["observations"], prior)
            prompt = prompt_for(method, public, previous, index, seed, original)
        path = folder / "raw" / oid / str(seed) / method / f"{index:03}.json"
        data = obtain(path, model, prompt, step_seed, method, len(menu), replay, time.perf_counter() - start)
        raw.append(data)
        output = decode_choice(data["response"], menu) if method in ACTION_METHODS else data["response"]
        outputs.append(output)
        graph = dataset.bench.parse_llm_response(output)
        valid = graph is not None and dataset.bench.validate_hypothesis(graph, public["observations"])
        if graph is not None:
            prior.append(graph)
        previous.append(dict(edges=graph.edges if graph is not None else None, valid=valid))
        trace.append(dict(index=index, decoded=output, valid=valid, menu_size=len(menu),
                          adaptive_active=method == "adaptive" and prompt != prompt_for(
                              "feedback", public, previous[:-1], index, seed, original)))
    prefixes = {str(k): score_prefix(dataset, row, outputs[:k]) for k in (4, 8, budget) if k <= budget}
    result = dict(method=method, case_id=oid, seed=seed, attempts=budget,
                  calls=0 if method == "action_uniform" else budget,
                  input_tokens=sum(v["input_tokens"] for v in raw),
                  output_tokens=sum(v["output_tokens"] for v in raw),
                  seconds=sum(v["seconds"] for v in raw),
                  preparation_s=sum(v["preparation_s"] for v in raw),
                  truncated=sum(v["done_reason"] == "length" for v in raw),
                  solution_count=row["n_compatible_graphs"], prefixes=prefixes,
                  activated=sum(t["adaptive_active"] for t in trace),
                  menu_sizes=[t["menu_size"] for t in trace] if method in ACTION_METHODS else [],
                  **prefixes[str(budget)])
    if not replay:
        save(folder / "traces" / oid / str(seed) / (method + ".json"), trace)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "experiments/causal-main.json").read_text())
    out = args.out or ROOT / "runs" / ("main-" + args.split)
    dataset = Dataset(args.upstream)
    model = None if args.replay else LocalModel()
    identity_path = out / "identity.json"
    existing = json.loads(identity_path.read_text()) if identity_path.exists() else None
    if args.replay and not existing:
        raise FileNotFoundError(identity_path)
    files = [*ROOT.glob("src/causal_*.py"), Path(__file__).resolve()]
    source = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    identity = dict(model=existing["model"] if args.replay else model.fingerprint(),
                    source=source, upstream=dataset.provenance, data=digest(dataset.cases),
                    protocol=digest(config), split=args.split)
    if existing:
        if any(existing.get(k) != v for k, v in identity.items()):
            raise ValueError("Run identity changed. Use a fresh --out folder or the frozen source.")
        identity = existing
    else:
        identity["commit"] = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        save(identity_path, identity)
    rows = []
    for oid in config[args.split]:
        for seed in config[args.split + "_seeds"]:
            for method in config["methods"]:
                cell = run_cell(dataset, model, dataset.cases[oid], method, seed, config["budget"], out, args.replay)
                rows.append(cell)
                print(args.split, oid, seed, method, "V/U/R", *[round(cell[k], 3) for k in ("V","U","R")], flush=True)
    summary = dict(protocol=config, split=args.split, identity=identity, rows=rows)
    if args.replay:
        if json.loads((out / "summary.json").read_text()) != summary:
            raise ValueError("Official replay differs from recorded summary")
        print("All cells replayed identically")
    else:
        save(out / "summary.json", summary)


if __name__ == "__main__":
    main()
