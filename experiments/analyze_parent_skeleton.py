"""Audit skeleton cells offline and compare them with the frozen parent-strata v1 controls."""
import argparse
import json
from pathlib import Path
import sys
from statistics import mean

import networkx as nx
import numpy as np

from run_causal import Dataset, ROOT, digest, save
from parent_strata import assemble, skeleton_plan

sys.path.insert(0, str(ROOT / "experiments"))
from causal_prompts import _reachability  # noqa: E402


def check(condition, detail):
    if not condition:
        raise ValueError(f"Integrity check failed: {detail}")


def audit_skeleton_cell(dataset, folder, cell, budget, variant):
    oid, seed = cell["case_id"], cell["seed"]
    case = dataset.cases[oid]
    truths = {frozenset(map(tuple, graph["edges"])) for graph in case["ground_truth_graphs"]}
    check(len(truths) == cell["solution_count"], (oid, "reference count"))
    public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
    plan = skeleton_plan(public, seed, budget, variant)
    base = _reachability(public, [])
    unique, recovered = set(), set()
    parsed = valid = 0
    curve = [0.0]
    for i in range(budget):
        path = folder / "raw" / oid / str(seed) / f"skeleton_{variant}" / f"{i:03}.json"
        record = json.loads(path.read_text())
        data = record["data"]
        check(digest(data) == record["data_sha256"], path)
        check(record["request_id"] == digest([data["prompt"], data["seed"], f"skeleton_{variant}", 0]), path)
        prompt = data["prompt"]
        check(plan[i]["prompt"] in prompt, (path, "scheduled stratum in actual prompt"))
        check(prompt.startswith(base.rsplit("\n", 1)[0] + "\n"), (path, "shared reachability base"))
        graph = dataset.bench.parse_llm_response(data["response"])
        final = assemble(plan[i], graph.edges if graph is not None else [])
        check(sorted(map(tuple, cell["assembled"][i])) == sorted(final), (path, "recorded assembly"))
        canonical = "Graph: " + ", ".join(f"{s}->{t}" for s, t in sorted(final)) or "Graph: No edges"
        evaluated = dataset.bench.parse_llm_response(canonical)
        if evaluated is not None:
            parsed += 1
            unique.add(final)
        dag = nx.DiGraph()
        dag.add_nodes_from(case["nodes"])
        dag.add_edges_from(final)
        compatible = all(
            nx.descendants(dag, obs["perturbed_node"]) == {v for v, effect in obs["effects"].items() if effect}
            for obs in case["observations"]
        )
        check(compatible == (final in truths), path)
        if evaluated is not None and compatible:
            valid += 1
            recovered.add(final)
        curve.append(len(recovered) / len(truths))
        q = i + 1
        if str(q) in cell["prefixes"]:
            expected = dict(V=valid / q, U=len(unique) / q, R=curve[-1],
                            valid=valid, recovered=len(recovered), parsed=parsed)
            check(all(cell["prefixes"][str(q)][k] == v for k, v in expected.items()), (path, "prefix scores"))
    check(cell["calls"] == budget, (oid, "calls"))
    for field in ("V", "U", "R", "recovered"):
        check(cell[field] == cell["prefixes"][str(budget)][field], (oid, field))
    grouped = {}
    order = []
    for stratum, edge_set in zip(plan, cell["assembled"], strict=True):
        key = (stratum["node"], tuple(stratum["parents"]))
        grouped.setdefault(key, []).append(frozenset(map(tuple, edge_set)))
    for group in grouped.values():
        order.extend(group)
    return dict(valid=valid, grouped_R_at={q: len(set(order[:int(q)]) - {frozenset()}) / len(truths)
                                           for q in cell["prefixes"]})


def summarize(folder, controls_folder, upstream, split, protocol_path):
    source = json.loads((folder / "summary.json").read_text())
    cfg = json.loads(protocol_path.read_text())
    check(source["protocol"] == cfg, "frozen skeleton protocol")
    check(source["split"] == split, "split")
    v1 = json.loads((controls_folder / "summary.json").read_text())
    v1_cfg = json.loads((ROOT / "experiments/parent-strata.json").read_text())
    check(v1["protocol"] == v1_cfg, "frozen parent-strata v1 protocol")
    check(v1["split"] == split, "controls split")
    check(cfg[split] == v1_cfg[split], "split alignment")
    check(cfg[f"{split}_seeds"] == v1_cfg[f"{split}_seeds"], "seed alignment")
    check(cfg["budget"] == v1_cfg["budget"], "budget alignment")
    cases, seeds = cfg[split], cfg[f"{split}_seeds"]
    methods = cfg["methods"]
    rows = {}
    for r in source["rows"]:
        rows.setdefault(r["method"], {})[(r["case_id"], r["seed"])] = r
    for method in methods:
        check(set(rows[method]) == {(c, s) for c in cases for s in seeds}, (method, "paired skeleton cells"))
    budget = cfg["budget"]
    dataset = Dataset(upstream)
    all_rows = {method: dict(rows[method]) for method in methods}
    audited = {}
    for method in methods:
        variant = method.split("_", 1)[1]
        audited[method] = {key: audit_skeleton_cell(dataset, folder, cell, budget, variant)
                           for key, cell in all_rows[method].items()}
    for method in ("official", "unstratified", "edge_count", "parent_set"):
        all_rows[method] = {(r["case_id"], r["seed"]): r for r in v1["rows"] if r["method"] == method}
    methods_report, case_r = {}, {}
    for method in ("official", "unstratified", "edge_count", "parent_set", *methods):
        group = list(all_rows[method].values())
        case_r[method] = {oid: mean(all_rows[method][oid, s]["R"] for s in seeds) for oid in cases}
        counts = {field: sum(r[field] for r in group)
                  for field in ("calls", "input_tokens", "output_tokens", "seconds")}
        counts["total_tokens"] = counts["input_tokens"] + counts["output_tokens"]
        report = dict(macro={k: mean(r[k] for r in group) for k in ("V", "U", "R")},
                      R_at={q: mean(r["prefixes"][q]["R"] for r in group) for q in group[0]["prefixes"]},
                      totals=counts, per_case_R=case_r[method])
        if method in ("edge_count", "parent_set"):
            report["assignment_hit_rate"] = sum(r["assignment_hits"] for r in group) / counts["calls"]
        if method in methods:
            report["valid_rate"] = mean(a["valid"] for a in audited[method].values()) / budget
        methods_report[method] = report
    replicates, bootstrap_seed = 10000, 33550336
    weights = np.random.default_rng(bootstrap_seed).integers(0, len(cases), (replicates, len(cases)))
    comparisons = {}
    for method in methods:
        for control in ("official", "unstratified", "edge_count", "parent_set"):
            deltas = {oid: r - case_r[control][oid] for oid, r in case_r[method].items()}
            values = np.array(list(deltas.values()))
            comparisons[f"{method}_minus_{control}"] = dict(
                mean_delta=mean(deltas.values()),
                ci95=np.quantile(values[weights].mean(axis=1), [.025, .975]).tolist(),
                wins=sum(int(v > 1e-12) for v in values), ties=sum(int(abs(v) <= 1e-12) for v in values),
                losses=sum(int(v < -1e-12) for v in values), per_case_delta=deltas)
    token_cap_rows = []
    matched = ("unstratified", "edge_count", "parent_set", *methods)
    for oid, seed in {(c, s) for c in cases for s in seeds}:
        cap = min(sum(all_rows[m][oid, seed][f] for f in ("input_tokens", "output_tokens")) for m in matched)
        for method in matched:
            row = all_rows[method][oid, seed]
            token_cap_rows.append(dict(case_id=oid, seed=seed, method=method, token_cap=cap,
                                       attempts=budget, R=row["R"]))
    return dict(split=split, n_cases=len(cases), seeds=seeds, budget=budget,
                n_skeleton_calls=len(source["rows"]) * budget,
                skeleton_protocol_sha256=digest(cfg), v1_protocol_sha256=digest(v1_cfg),
                generation_commit=source["identity"]["commit"],
                methods=methods_report, comparisons=comparisons,
                bootstrap=dict(replicates=replicates, seed=bootstrap_seed,
                               unit="paired case after averaging its seeds; percentile interval"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    methods = json.loads(args.protocol.read_text())["methods"]
    report = summarize(ROOT / "runs" / f"skeleton-{args.split}",
                       ROOT / "runs" / f"parent-{args.split}",
                       args.upstream, args.split, args.protocol)
    save(args.out, report)
    print(f"{args.split}: compared {len(methods)} skeleton method(s) against 4 frozen controls")
