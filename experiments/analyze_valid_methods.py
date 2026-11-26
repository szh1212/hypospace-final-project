"""Three-metric (V/U/R) comparison for the validity-filtered and joint variants.

Controls are replayed from the frozen parent-strata v1 raw (budget 16, seeds
17/42); the two new variants are replayed from runs/skeleton-valid-test
(budget 16, seeds 17/42/2026). Prefixes at 13 calls support the SZH-aligned
comparison. Paired bootstrap covers all three metrics.
"""
import argparse
import json
from pathlib import Path
import sys
from statistics import mean

import networkx as nx
import numpy as np

from run_causal import ROOT, Dataset, digest
from parent_strata import filtered_completion, joint_skeleton_plan, skeleton_plan

sys.path.insert(0, str(ROOT / "experiments"))

CONTROLS = ("official", "unstratified", "edge_count", "parent_set")
NEW_METHODS = ("skeleton_complete_forced_valid", "skeleton_complete_forced_valid_joint")
SZ_BASELINE = dict(V=0.7851851851851851, U=0.2164609053497942, R=0.17448559670781896)


def check(condition, detail):
    if not condition:
        raise ValueError(f"Integrity check failed: {detail}")


def truth_sets(case):
    return {frozenset(map(tuple, graph["edges"])) for graph in case["ground_truth_graphs"]}


def compatible(dataset, case, edges):
    dag = nx.DiGraph()
    dag.add_nodes_from(case["nodes"])
    dag.add_edges_from(edges)
    return len(edges) <= case["max_edges"] and all(
        nx.descendants(dag, obs["perturbed_node"]) == {v for v, effect in obs["effects"].items() if effect}
        for obs in case["observations"])


def cell_metrics(dataset, case, oid, seed, method, folder, budget):
    truths = truth_sets(case)
    public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
    variant = method.split("_", 1)[1]
    plan = (joint_skeleton_plan(public, seed, budget) if variant == "complete_forced_valid_joint"
            else skeleton_plan(public, seed, budget, variant))
    unique, recovered, valid = set(), set(), 0
    curve = {"4": None, "8": None, "13": None, "16": None}
    for i in range(budget):
        record = json.loads((folder / oid / str(seed) / method / f"{i:03}.json").read_text())
        data = record["data"]
        check(digest(data) == record["data_sha256"], (folder, oid, seed, method, i))
        graph = dataset.bench.parse_llm_response(data["response"])
        parsed = graph.edges if graph is not None else []
        final = filtered_completion(plan[i], parsed, public)
        unique.add(final)
        if compatible(dataset, case, final):
            check(final in truths, (folder, oid, seed, method, i))
            valid += 1
            recovered.add(final)
        for k in curve:
            if k is not None and i + 1 == int(k):
                curve[k] = dict(V=valid / (i + 1), U=len(unique) / (i + 1),
                                R=len(recovered) / len(truths))
    for k, value in curve.items():
        if value is None and int(k) <= budget:
            raise ValueError((oid, seed, method, k, "missing prefix"))
    return curve


def replay_control(dataset, case, oid, seed, method, budget):
    truths = truth_sets(case)
    folder = ROOT / "runs/parent-test" / "raw"
    unique, recovered, valid = set(), set(), 0
    curve = {}
    for i in range(budget):
        record = json.loads((folder / oid / str(seed) / method / f"{i:03}.json").read_text())
        data = record["data"]
        check(digest(data) == record["data_sha256"], (oid, seed, method, i))
        graph = dataset.bench.parse_llm_response(data["response"])
        if graph is not None:
            edges = frozenset(map(tuple, graph.edges))
            unique.add(edges)
            if compatible(dataset, case, edges):
                check(edges in truths, (oid, seed, method, i))
                valid += 1
                recovered.add(edges)
        for k in ("4", "8", "13", "16"):
            if i + 1 == int(k):
                curve[k] = dict(V=valid / (i + 1), U=len(unique) / (i + 1),
                                R=len(recovered) / len(truths))
    return curve


def bootstrap_contrast(method_case, control_case, cases, metric):
    deltas = {oid: method_case[oid][metric] - control_case[oid][metric] for oid in cases}
    values = np.array(list(deltas.values()))
    rng = np.random.default_rng(33550336)
    weights = rng.integers(0, len(cases), (10000, len(cases)))
    return dict(mean_delta=mean(deltas.values()),
                ci95=np.quantile(values[weights].mean(axis=1), [.025, .975]).tolist(),
                wins=sum(int(v > 1e-12) for v in values),
                ties=sum(int(abs(v) <= 1e-12) for v in values),
                losses=sum(int(v < -1e-12) for v in values),
                per_case_delta=deltas)


def summarize(upstream):
    protocol = json.loads((ROOT / "experiments/parent-skeleton-valid.json").read_text())
    cases, seeds = protocol["test"], protocol["test_seeds"]
    budget = protocol["budget"]
    dataset = Dataset(upstream)
    rows = {}
    for oid in cases:
        case = dataset.cases[oid]
        for seed in (17, 42):
            for method in CONTROLS:
                rows.setdefault(method, []).append((oid, seed, replay_control(dataset, case, oid, seed, method, budget)))
        for method in NEW_METHODS:
            folder = ROOT / "runs/skeleton-valid-test" / "raw"
            for seed in seeds:
                rows.setdefault(method, []).append(
                    (oid, seed, cell_metrics(dataset, case, oid, seed, method, folder, budget)))
    report = {}
    for method, entries in rows.items():
        by_case = {oid: {} for oid in cases}
        for oid, seed, curve in entries:
            by_case[oid][seed] = curve
        for k in ("4", "8", "13", "16"):
            for metric in ("V", "U", "R"):
                key = f"{metric}{k}_2seeds"
                report.setdefault(method, {})[key] = mean(
                    mean(by_case[oid][s][k][metric] for s in (17, 42)) for oid in cases)
        if method in NEW_METHODS:
            for k in ("4", "8", "13"):
                for metric in ("V", "U", "R"):
                    report[method][f"{metric}{k}_3seeds"] = mean(
                        mean(by_case[oid][s][k][metric] for s in seeds) for oid in cases)
    comparisons = {}
    for method in NEW_METHODS:
        for control in CONTROLS:
            for k in ("13", "16"):
                for metric in ("V", "U", "R"):
                    m = {oid: mean(rows_row(rows, method, oid, s)[k][metric] for s in (17, 42))
                         for oid in cases}
                    c = {oid: mean(rows_row(rows, control, oid, s)[k][metric] for s in (17, 42))
                         for oid in cases}
                    comparisons[f"{method}_minus_{control}_{metric}{k}"] = bootstrap_contrast(m, c, cases, "x")
    # per-case curves indexed for bootstrap contrast
    method_curves, control_curves = {}, {}
    for method in (*NEW_METHODS, *CONTROLS):
        method_curves[method] = {oid: {s: curve for (o, s, curve) in rows[method] if o == oid}
                                 for oid in cases}
    comparisons = {}
    for method in NEW_METHODS:
        for control in CONTROLS:
            for k in ("13", "16"):
                for metric in ("V", "U", "R"):
                    m = {oid: mean(method_curves[method][oid][s][k][metric] for s in (17, 42)) for oid in cases}
                    c = {oid: mean(method_curves[control][oid][s][k][metric] for s in (17, 42)) for oid in cases}
                    comparisons[f"{method}_minus_{control}_{metric}@{k}"] = bootstrap_contrast(m, c, cases, metric)
    szh = {}
    for method in NEW_METHODS:
        szh[method] = {metric: report[method][f"{metric}13_3seeds"] - SZ_BASELINE[metric]
                       for metric in ("V", "U", "R")}
    return dict(protocol=protocol, methods=report, comparisons=comparisons,
                szh_baseline=dict(reference=SZ_BASELINE,
                                  note="3d gravity domain; cross-domain nominal deltas only",
                                  forced_valid_minus=szh[NEW_METHODS[0]],
                                  joint_minus=szh[NEW_METHODS[1]],
                                  prefix="R@13, seeds 17/42/2026"))


def rows_row(rows, method, oid, seed):
    return next(curve for (o, s, curve) in rows[method] if o == oid and s == seed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    args = parser.parse_args()
    report = summarize(args.upstream)
    from run_causal import save
    save(ROOT / "docs/parent-skeleton-valid.json", report)
    for method, values in report["methods"].items():
        print(method, {k: round(v, 4) for k, v in values.items() if "2seeds" in k and k.startswith(("V", "U", "R")) and k[1] in "134"})
    for method in NEW_METHODS:
        print(method, "vs SZH:", {k: round(v, 4) for k, v in report["szh_baseline"].get(
            "joint_minus" if "joint" in method else "forced_valid_minus", {}).items()})
