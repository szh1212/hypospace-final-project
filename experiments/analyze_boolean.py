"""Three-metric (V/U/R) paired comparison for the boolean gene-interaction run.

All four methods share the same cases, seeds, budget and model; the official
baseline replays the upstream prompt loop with accumulated history, and the
other three replay the hierarchical prompts plus their deterministic assembly.
Paired bootstrap (per-case deltas, 10,000 case resamples) covers V, U and R at
the 16-call budget and the 13-call prefix.
"""
import argparse
import json
import sys
from pathlib import Path
from statistics import mean

import numpy as np

from run_causal import ROOT, digest
from boolean_benchmark import COLLECTION, Dataset, load_official
from boolean_prompts import completion_prompt, skeleton_prompt
from boolean_space import assemble, completion_plan, skeleton_plan

CONTROLS = ("official", "completion")
METHODS = ("skeleton", "skeleton_valid")
BUDGET = 16
PREFIXES = ("4", "8", "13", "16")
RESAMPLE_SEED = 33550336
RESAMPLES = 10000


def check(condition, detail):
    if not condition:
        raise ValueError(f"Integrity check failed: {detail}")


def cell_outputs(dataset, case, oid, seed, method, folder):
    """Recompute each method's evaluated outputs from the raw records."""
    public = {k: case[k] for k in ("observations", "variables", "operators", "max_depth")}
    outputs = []
    raw = folder / "raw" / oid / str(seed) / method
    if method == "official":
        _, dataset_module = load_official(dataset._upstream)
        observations = [dataset_module.BooleanObservation(obs["inputs"], obs["output"])
                        for obs in case["observations"]]
        prior = []
        for index in range(BUDGET):
            record = json.loads((raw / f"{index:03}.json").read_text())
            data = record["data"]
            check(digest(data) == record["data_sha256"], (oid, seed, method, index))
            prompt = dataset.bench.create_prompt(observations, prior)
            check(prompt == data["prompt"], (oid, seed, method, index, "prompt mismatch"))
            parsed = dataset.bench.parse_llm_response(data["response"])
            if parsed:
                prior.append(parsed)
            outputs.append(data["response"])
        return outputs, None
    if method == "completion":
        conditions = completion_plan(dataset._upstream, public, seed, BUDGET)
        prompts = [completion_prompt(public, c) for c in conditions]
    else:
        conditions = skeleton_plan(dataset._upstream, public, seed, BUDGET)
        prompts = [skeleton_prompt(public, c) for c in conditions]
    kept = 0
    for index, (condition, prompt) in enumerate(zip(conditions, prompts, strict=True)):
        record = json.loads((raw / f"{index:03}.json").read_text())
        data = record["data"]
        check(digest(data) == record["data_sha256"], (oid, seed, method, index))
        check(prompt == data["prompt"], (oid, seed, method, index, "prompt mismatch"))
        final = assemble(dataset, condition, data["response"], method)
        if method == "skeleton_valid" and final is not None:
            from boolean_space import parse_expression
            parsed = parse_expression(dataset, data["response"])
            if parsed is not None:
                from boolean_space import _matches
                if _matches(parsed["table"], condition["completion"]):
                    kept += 1
        outputs.append(f"Expression: {final}" if final else "")
    return outputs, dict(model_kept=kept, calls=BUDGET)


def curve(dataset, case, outputs):
    scored = {}
    for k in PREFIXES:
        value = dataset.score(case, outputs[: int(k)])
        scored[k] = dict(V=value["valid_rate"], U=value["novelty_rate"],
                         R=value["recovery_rate"])
    return scored


def bootstrap_contrast(method_case, control_case, cases, metric):
    values = np.array([method_case[oid] - control_case[oid] for oid in cases])
    rng = np.random.default_rng(RESAMPLE_SEED)
    weights = rng.integers(0, len(cases), (RESAMPLES, len(cases)))
    return dict(mean_delta=float(mean(values)),
                ci95=np.quantile(values[weights].mean(axis=1), [.025, .975]).tolist(),
                wins=int(sum(v > 1e-12 for v in values)),
                ties=int(sum(abs(v) <= 1e-12 for v in values)),
                losses=int(sum(v < -1e-12 for v in values)),
                per_case_delta={oid: float(v) for oid, v in zip(cases, values)})


def summarize(folder, split="test"):
    protocol = json.loads((ROOT / "experiments/boolean-skeleton.json").read_text())
    cases, seeds = protocol[split], protocol[split + "_seeds"]
    dataset = Dataset(ROOT / ".cache/hypospace", ROOT / ".cache" / COLLECTION)
    methods = (*CONTROLS, *METHODS)
    entries = {}
    compliance = {}
    for oid in cases:
        case = dataset.cases[oid]
        for seed in seeds:
            for method in methods:
                outputs, diagnostic = cell_outputs(dataset, case, oid, seed, method, folder)
                entries.setdefault(method, []).append((oid, seed, curve(dataset, case, outputs)))
                if diagnostic is not None:
                    compliance.setdefault(method, []).append(diagnostic["model_kept"] / BUDGET)
    report = {}
    for method in methods:
        by_case = {oid: {} for oid in cases}
        for oid, seed, result in entries[method]:
            by_case[oid][seed] = result
        for k in PREFIXES:
            for metric in ("V", "U", "R"):
                report.setdefault(method, {})[f"{metric}@{k}"] = mean(
                    mean(by_case[oid][s][k][metric] for s in seeds) for oid in cases)
    comparisons = {}
    for method in METHODS:
        for control in CONTROLS:
            for k in ("13", "16"):
                for metric in ("V", "U", "R"):
                    m = {oid: mean(next(r for (o, s, r) in entries[method] if o == oid and s == seed)[k][metric]
                                   for seed in seeds) for oid in cases}
                    c = {oid: mean(next(r for (o, s, r) in entries[control] if o == oid and s == seed)[k][metric]
                                   for seed in seeds) for oid in cases}
                    comparisons[f"{method}_minus_{control}_{metric}@{k}"] = bootstrap_contrast(
                        m, c, cases, metric)
    per_case = {}
    for oid in cases:
        per_case[oid] = {}
        for method in methods:
            per_case[oid][method] = {
                metric: mean(next(r for (o, s, r) in entries[method] if o == oid and s == seed)["16"][metric]
                             for seed in seeds)
                for metric in ("V", "U", "R")}
    return dict(protocol=protocol, methods=report, comparisons=comparisons,
                per_case=per_case,
                compliance=({m: mean(v) for m, v in compliance.items()}
                            if compliance else None))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test"], default="test")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    folder = args.out or ROOT / "runs" / ("boolean-" + args.split)
    report = summarize(folder, args.split)
    save_path = ROOT / ".cache" / f"boolean-{args.split}.json"
    from run_causal import save
    save(save_path, report)
    for method, values in report["methods"].items():
        print(method, {k: round(v, 4) for k, v in values.items() if k.endswith("@16")})
    print("\npaired comparisons (method_minus_control at 16 calls):")
    for key, value in report["comparisons"].items():
        if "@16" in key:
            print(f"  {key}: mean={value['mean_delta']:+.4f} "
                  f"ci=[{value['ci95'][0]:+.4f}, {value['ci95'][1]:+.4f}] "
                  f"w/t/l={value['wins']}/{value['ties']}/{value['losses']}")
