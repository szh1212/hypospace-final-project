"""Summarize complete paired runs; one statistical unit is an observation."""
import argparse
import itertools
import json
import math
import random
from pathlib import Path
from statistics import mean

RATES = ("V", "U", "R")
COUNTS = ("attempts", "calls", "input_tokens", "output_tokens", "seconds",
          "parsed", "valid", "recovered", "activated")


def verify_cells(rows, protocol, split):
    expected = set(itertools.product(protocol["methods"], protocol[split], protocol[f"{split}_seeds"]))
    actual = {(r["method"], r["case_id"], r["seed"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("Missing, extra or duplicate paired cells")
    b = protocol["budget"]
    for r in rows:
        if r["attempts"] != b or any(r[k] < 0 for k in COUNTS):
            raise ValueError("Budget or resource total invalid")
        if not 0 <= r["recovered"] <= r["valid"] <= r["parsed"] <= b:
            raise ValueError("Inconsistent outcome counts")
        if not math.isclose(r["V"], r["valid"] / b) or not math.isclose(r["R"], r["recovered"] / r["solution_count"]):
            raise ValueError("Invalid metric denominator")
        if any(r["prefixes"][str(b)][k] != r[k] for k in RATES):
            raise ValueError("Terminal and full-budget scores differ")
    return {"actual_cells": len(rows), "n_cases": len(protocol[split])}


def summarize(source):
    cfg, split, rows = source["protocol"], source["split"], source["rows"]
    counts = verify_cells(rows, cfg, split)
    methods = {}
    case_r = {}
    for name in cfg["methods"]:
        group = [r for r in rows if r["method"] == name]
        totals = {k: sum(r[k] for r in group) for k in COUNTS}
        totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
        case_r[name] = {oid: mean(r["R"] for r in group if r["case_id"] == oid) for oid in cfg[split]}
        methods[name] = {"macro": {k: mean(r[k] for r in group) for k in RATES},
                         "totals": totals, "per_case_R": case_r[name],
                         "R_at": {k: mean(r["prefixes"][k]["R"] for r in group) for k in group[0]["prefixes"]},
                         "preparation_s": sum(r.get("preparation_s", 0) for r in group)}
    pairs = [(base, name) for base in ("official","edge_count") for name in methods
             if base in methods and name not in (base,"official")]
    pairs += [(a,b) for a,b in (("reachability","feedback"), ("feedback","adaptive"),
                                ("structural_cycle","adaptive"), ("action_uniform","action_llm"))
              if a in methods and b in methods]
    contrasts = []
    for base, name in pairs:
        deltas = {k: value-case_r[base][k] for k,value in case_r[name].items()}
        values = list(deltas.values())
        rng = random.Random(33550336)
        samples = sorted(mean(rng.choices(values, k=len(values))) for _ in range(2000))
        contrasts.append(dict(method=name,baseline=base,n_cases=len(values),per_case_deltas=deltas,
                              mean_delta=mean(values),ci95=[samples[49],samples[1949]]))
    return dict(split=split, counts=counts, identity=source["identity"], methods=methods, contrasts=contrasts,
                bootstrap={"replicates":2000,"seed":33550336,"unit":"observation after averaging seeds"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = summarize(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
