"""Audit raw parent-strata calls offline and report paired recovery on a frozen split."""
import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
import re
from statistics import mean

import networkx as nx
import numpy as np

from run_causal import Dataset, ROOT, digest, save
from parent_strata import parent_plan


def check(condition, detail):
    if not condition:
        raise ValueError(f"Integrity check failed: {detail}")


def grouped_order_recovery(plan, valid_graphs, n_truths, prefixes):
    grouped = {}
    for stratum, graph in zip(plan, valid_graphs, strict=True):
        key = (stratum["node"], tuple(stratum["parents"]))
        grouped.setdefault(key, []).append(graph)
    order = [graph for group in grouped.values() for graph in group]
    return {q: len(set(order[:int(q)]) - {None}) / n_truths for q in prefixes}


def audit_cell(dataset, folder, cell, budget):
    oid, seed, method = cell["case_id"], cell["seed"], cell["method"]
    case = dataset.cases[oid]
    truths = {frozenset(map(tuple, graph["edges"])) for graph in case["ground_truth_graphs"]}
    check(len(truths) == cell["solution_count"], (oid, "reference count"))
    public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
    plan = parent_plan(public, seed, budget)
    anchor = plan[0]["node"]
    def parents_at_anchor(edges):
        return frozenset(tail for tail, head in edges if head == anchor)
    possible_parent_sets = {parents_at_anchor(edges) for edges in truths}
    unique, recovered = set(), set()
    parsed = valid = assignment_hits = valid_hits = 0
    valid_graphs = []
    cumulative_tokens = [0]
    recovery_curve = [0.]
    seeds = []
    tokens = Counter()
    for i in range(budget):
        path = folder / "raw" / oid / str(seed) / method / f"{i:03}.json"
        record = json.loads(path.read_text())
        data = record["data"]
        check(digest(data) == record["data_sha256"], path)
        check(record["request_id"] == digest([data["prompt"], data["seed"], method, 0]), path)
        if method == "parent_set":
            check(plan[i]["prompt"] in data["prompt"], (path, "scheduled stratum in actual prompt"))
        seeds.append(data["seed"])
        for field in ("input_tokens", "output_tokens"):
            tokens[field] += data[field]
        cumulative_tokens.append(tokens.total())
        graph = dataset.bench.parse_llm_response(data["response"])
        valid_graph = None
        if graph is not None:
            parsed += 1
            edges = frozenset(map(tuple, graph.edges))
            unique.add(edges)
            dag = nx.DiGraph()
            dag.add_nodes_from(case["nodes"])
            dag.add_edges_from(edges)
            compatible = all(
                nx.descendants(dag, obs["perturbed_node"]) == {v for v, effect in obs["effects"].items() if effect}
                for obs in case["observations"]
            )
            check(compatible == (edges in truths), path)
            if compatible:
                valid += 1
                recovered.add(edges)
                valid_graph = edges
            if method == "parent_set":
                assigned = plan[i]
                hit = parents_at_anchor(edges) == set(assigned["parents"])
                assignment_hits += hit
                valid_hits += hit and compatible
            elif method == "edge_count":
                specified = re.search(r"Use exactly (\d+) directed edges\.", data["prompt"])
                check(specified is not None, (path, "requested edge count"))
                assignment_hits += len(edges) == int(specified.group(1))
        valid_graphs.append(valid_graph)
        recovery_curve.append(len(recovered) / len(truths))
        q = i + 1
        if str(q) in cell["prefixes"]:
            expected = dict(V=valid / q, U=len(unique) / q, R=recovery_curve[-1],
                            valid=valid, recovered=len(recovered), parsed=parsed)
            check(all(cell["prefixes"][str(q)][k] == v for k, v in expected.items()), (path, "prefix scores"))
    check(all(cell[field] == value for field, value in tokens.items()), (oid, method, "tokens"))
    check(cell["calls"] == budget, (oid, method, "calls"))
    for field in ("V", "U", "R", "recovered"):
        check(cell[field] == cell["prefixes"][str(budget)][field], (oid, method, field))
    if method in {"parent_set", "edge_count"}:
        check(assignment_hits == cell["assignment_hits"], (oid, method, "stratum compliance"))
    grouped = None
    if method == "parent_set":
        grouped = grouped_order_recovery(plan, valid_graphs, len(truths), cell["prefixes"])
        check(grouped[str(budget)] == cell["R"], (oid, "full-budget grouped order"))
    parent_sets_recovered = {parents_at_anchor(edges) for edges in recovered}
    return dict(cost=cumulative_tokens, R=recovery_curve, seeds=seeds,
                recovered_parent_sets=len(parent_sets_recovered),
                parent_set_coverage=len(parent_sets_recovered) / len(possible_parent_sets),
                valid_assignment_hits=valid_hits, grouped_R_at=grouped)


def contrast(case_r, method, baseline, weights):
    deltas = {oid: r - case_r[baseline][oid] for oid, r in case_r[method].items()}
    values = np.array(list(deltas.values()))
    estimates = values[weights].mean(axis=1)
    return dict(mean_delta=mean(deltas.values()), ci95=np.quantile(estimates, [.025, .975]).tolist(),
                wins=sum(int(v > 1e-12) for v in values), ties=sum(int(abs(v) <= 1e-12) for v in values),
                losses=sum(int(v < -1e-12) for v in values), per_case_delta=deltas)


def summarize(folder, upstream, split):
    source = json.loads((folder / "summary.json").read_text())
    cfg = source["protocol"]
    check(cfg == json.loads((ROOT / "experiments/parent-strata.json").read_text()), "frozen protocol")
    check(source["split"] == split, "split")
    cases, seeds, methods = cfg[split], cfg[f"{split}_seeds"], cfg["methods"]
    rows = {(r["case_id"], r["seed"], r["method"]): r for r in source["rows"]}
    check(len(rows) == len(source["rows"]) and set(rows) == set(product(cases, seeds, methods)), "paired cells")
    budget = cfg["budget"]
    dataset = Dataset(upstream)
    audited = {key: audit_cell(dataset, folder, cell, budget) for key, cell in rows.items()}
    methods_report, case_r = {}, {}
    for method in methods:
        group = [r for (_, _, m), r in rows.items() if m == method]
        case_r[method] = {oid: mean(rows[oid, s, method]["R"] for s in seeds) for oid in cases}
        counts = {field: sum(r[field] for r in group)
                  for field in ("calls", "input_tokens", "output_tokens", "seconds")}
        counts["total_tokens"] = counts["input_tokens"] + counts["output_tokens"]
        obs_groups = {n: [oid for oid in cases if len(dataset.cases[oid]["observations"]) == n] for n in (1, 2)}
        report = dict(macro={k: mean(r[k] for r in group) for k in ("V", "U", "R")},
                      R_at={q: mean(r["prefixes"][q]["R"] for r in group) for q in group[0]["prefixes"]},
                      totals=counts, per_case_R=case_r[method],
                      by_observations={n: dict(n_cases=len(ids), R=mean(case_r[method][oid] for oid in ids))
                                       for n, ids in obs_groups.items() if ids})
        method_audits = [a for (_, _, m), a in audited.items() if m == method]
        report["mean_distinct_valid_parent_sets"] = mean(a["recovered_parent_sets"] for a in method_audits)
        report["mean_valid_parent_set_coverage"] = mean(a["parent_set_coverage"] for a in method_audits)
        if method in {"edge_count", "parent_set"}:
            report["assignment_hit_rate"] = sum(r["assignment_hits"] for r in group) / counts["calls"]
        if method == "parent_set":
            report["valid_and_assigned_rate"] = sum(a["valid_assignment_hits"] for (_, _, m), a in audited.items()
                                                     if m == method) / counts["calls"]
        methods_report[method] = report

    replicates, bootstrap_seed = 10000, 33550336
    weights = np.random.default_rng(bootstrap_seed).integers(0, len(cases), (replicates, len(cases)))
    comparisons = {m: contrast(case_r, "parent_set", m, weights) for m in methods if m != "parent_set"}
    round_robin = methods_report["parent_set"]["R_at"]
    grouped = {q: mean(a["grouped_R_at"][q] for (_, _, method), a in audited.items() if method == "parent_set")
               for q in round_robin}
    order_sensitivity = dict(rule="Post-hoc reordering of the same complete parent-set records. Group strata by "
                                  "first scheduled appearance, preserving within-stratum order. Each response "
                                  "and its RNG seed move together. Identical per-stratum quota and terminal R. "
                                  "Only the prefix order of these observed draws is evaluated.",
                             round_robin_R_at=round_robin, grouped_R_at=grouped,
                             round_robin_minus_grouped={q: r - grouped[q] for q,r in round_robin.items()})
    matched = [m for m in methods if m != "official"]
    cap_rows = []
    for oid, seed in product(cases, seeds):
        paired_seeds = {tuple(audited[oid, seed, m]["seeds"]) for m in methods}
        check(len(paired_seeds) == 1, (oid, seed, "per-attempt seed schedule"))
        cap = min(audited[oid, seed, m]["cost"][-1] for m in matched)
        for method in matched:
            seq = audited[oid, seed, method]
            prefix = max(i for i, tokens in enumerate(seq["cost"]) if tokens <= cap)
            cap_rows.append(dict(case_id=oid, seed=seed, method=method, token_cap=cap, attempts=prefix,
                                 R=seq["R"][prefix], tokens=seq["cost"][prefix]))
    capped = {}
    for method in matched:
        subset = [r for r in cap_rows if r["method"] == method]
        capped[method] = dict(R=mean(r["R"] for r in subset), mean_attempts=mean(r["attempts"] for r in subset))
    return dict(split=split, protocol_sha256=digest(cfg), generation_commit=source["identity"]["commit"],
                n_cases=len(cases), seeds=seeds, budget=budget,
                n_raw_calls=len(rows) * budget, methods=methods_report, parent_set_minus=comparisons,
                order_sensitivity=order_sensitivity,
                bootstrap=dict(replicates=replicates, seed=bootstrap_seed,
                               unit="paired case after averaging its seeds; percentile interval"),
                posthoc_token_cap=dict(rule="Smallest full-run input + output tokens of the three matched-prompt "
                                            "methods on each case and seed. Keep the longest consecutive prefix.",
                                       methods=capped, rows=cap_rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    args = parser.parse_args()
    report = summarize(ROOT / "runs" / f"parent-{args.split}", args.upstream, args.split)
    save(ROOT / "docs" / f"parent-strata-{args.split}.json", report)
    print(f"{args.split}: verified {report['n_raw_calls']} calls on {report['n_cases']} cases")
