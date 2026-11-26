"""R@13 aligned-budget comparison: forced skeleton vs frozen controls and the SZH 3d baseline."""
import argparse
import json
from pathlib import Path
import sys
from statistics import mean

import networkx as nx
import numpy as np

from run_causal import ROOT, Dataset, digest, save
from parent_strata import enforce_limit, skeleton_plan

sys.path.insert(0, str(ROOT / "experiments"))

CONTROLS = ("official", "unstratified", "edge_count", "parent_set")
SZ_R = 0.17448559670781896  # SZH 3d adapted baseline macro recovery (docs/figures/baseline/metrics.json)


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


def replay_control(dataset, case, oid, seed, method, budget=13):
    folder = ROOT / "runs/parent-test" / "raw" / oid / str(seed) / method
    truths = truth_sets(case)
    unique, recovered, valid, parsed = set(), set(), 0, 0
    for i in range(budget):
        record = json.loads((folder / f"{i:03}.json").read_text())
        data = record["data"]
        check(digest(data) == record["data_sha256"], folder)
        graph = dataset.bench.parse_llm_response(data["response"])
        if graph is None:
            continue
        parsed += 1
        edges = frozenset(map(tuple, graph.edges))
        unique.add(edges)
        if compatible(dataset, case, edges):
            check(edges in truths, folder)
            valid += 1
            recovered.add(edges)
    return dict(valid=valid, parsed=parsed, unique=len(unique), recovered=len(recovered),
                R=len(recovered) / len(truths))


def replay_forced(dataset, case, oid, seed, budget=13):
    folder = ROOT / "runs/skeleton-aligned-test" / "raw" / oid / str(seed) / "skeleton_complete_forced"
    public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
    plan = skeleton_plan(public, seed, budget, "complete_forced")
    truths = truth_sets(case)
    unique, recovered, valid, parsed = set(), set(), 0, 0
    for i in range(budget):
        record = json.loads((folder / f"{i:03}.json").read_text())
        data = record["data"]
        check(digest(data) == record["data_sha256"], folder)
        check(record["request_id"] == digest([data["prompt"], data["seed"], "skeleton_complete_forced", 0]), folder)
        check(plan[i]["prompt"] in data["prompt"], folder)
        graph = dataset.bench.parse_llm_response(data["response"])
        final = enforce_limit(plan[i], graph.edges if graph is not None else [], public["max_edges"])
        if graph is not None:
            parsed += 1
        unique.add(final)
        if compatible(dataset, case, final):
            check(final in truths, folder)
            valid += 1
            recovered.add(final)
    return dict(valid=valid, parsed=parsed, unique=len(unique), recovered=len(recovered),
                R=len(recovered) / len(truths))


def summarize(upstream):
    protocol = json.loads((ROOT / "experiments/parent-skeleton-aligned.json").read_text())
    cases, seeds = protocol["test"], protocol["test_seeds"]
    dataset = Dataset(upstream)
    rows = {}
    for oid in cases:
        case = dataset.cases[oid]
        for seed in (17, 42):
            for method in CONTROLS:
                rows.setdefault(method, []).append((oid, seed, replay_control(dataset, case, oid, seed, method)))
        for seed in seeds:
            rows.setdefault("skeleton_complete_forced", []).append(
                (oid, seed, replay_forced(dataset, case, oid, seed)))
    methods_report = {}
    for method, entries in rows.items():
        by_case = {}
        for oid, seed, r in entries:
            by_case.setdefault(oid, {})[seed] = r
        per_case_2 = {oid: mean(v[s]["R"] for s in (17, 42)) for oid, v in by_case.items()}
        report = dict(macro_R_2seeds=mean(per_case_2.values()), per_case_R=per_case_2,
                      V=mean(r["valid"] / protocol["budget"] for oid, s, r in entries if s in (17, 42)),
                      U=mean(r["unique"] / protocol["budget"] for oid, s, r in entries if s in (17, 42)))
        if method == "skeleton_complete_forced":
            per_case_3 = {oid: mean(v[s]["R"] for s in seeds) for oid, v in by_case.items()}
            report["macro_R_3seeds"] = mean(per_case_3.values())
            report["per_case_R_3seeds"] = per_case_3
            report["V_3seeds"] = mean(r["valid"] / protocol["budget"] for oid, s, r in entries)
            report["U_3seeds"] = mean(r["unique"] / protocol["budget"] for oid, s, r in entries)
        methods_report[method] = report
    forced2 = methods_report["skeleton_complete_forced"]["per_case_R"]
    replicates, bootstrap_seed = 10000, 33550336
    weights = np.random.default_rng(bootstrap_seed).integers(0, len(cases), (replicates, len(cases)))
    comparisons = {}
    for control in CONTROLS:
        deltas = {oid: forced2[oid] - methods_report[control]["per_case_R"][oid] for oid in cases}
        values = np.array(list(deltas.values()))
        comparisons[f"forced@13_minus_{control}@13"] = dict(
            mean_delta=mean(deltas.values()),
            ci95=np.quantile(values[weights].mean(axis=1), [.025, .975]).tolist(),
            wins=sum(int(v > 1e-12) for v in values), ties=sum(int(abs(v) <= 1e-12) for v in values),
            losses=sum(int(v < -1e-12) for v in values), per_case_delta=deltas)
    forced3 = methods_report["skeleton_complete_forced"]["macro_R_3seeds"]
    return dict(protocol=json.loads((ROOT / "experiments/parent-skeleton-aligned.json").read_text()),
                n_cases=len(cases), budget=13, seeds=seeds, methods=methods_report,
                comparisons=comparisons,
                szh_baseline=dict(R=SZ_R, domain="3d gravity, 585 calls, 45 tasks, 13 queries per task, seeds 17/42/2026",
                                  forced_minus_szh_2seeds=forced2 and mean(forced2.values()) - SZ_R,
                                  forced_minus_szh_3seeds=forced3 - SZ_R),
                bootstrap=dict(replicates=replicates, seed=bootstrap_seed,
                               unit="paired case after averaging its seeds; percentile interval"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    args = parser.parse_args()
    report = summarize(args.upstream)
    save(ROOT / ".cache/parent-skeleton-aligned.json", report)
    f3 = report["methods"]["skeleton_complete_forced"]
    print(f"forced@13 macro R (3 seeds): {f3['macro_R_3seeds']:.4f}")
    print(f"forced@13 macro R (2 seeds): {f3['macro_R_2seeds']:.4f}")
    for key, value in report["comparisons"].items():
        print(key, f"mean_delta={value['mean_delta']:.4f} ci95={[round(x, 4) for x in value['ci95']]} "
              f"w/t/l={value['wins']}/{value['ties']}/{value['losses']}")
    print("vs SZH baseline:", report["szh_baseline"])
