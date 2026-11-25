"""Replay direct-generation methods under the same token allowance for each case/seed."""
import argparse
import json
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from causal_benchmark import Dataset


def summarize(folder, upstream):
    study = json.loads((folder / "summary.json").read_text())
    cfg = study["protocol"]
    methods = [m for m in cfg["methods"] if m not in {"action_llm", "action_uniform"}]
    dataset = Dataset(upstream)
    rows = []
    for oid in cfg[study["split"]]:
        for seed in cfg[study["split"] + "_seeds"]:
            sequences = {}
            totals = {}
            for method in methods:
                base = folder / "raw" / oid / str(seed) / method
                seq = [json.loads((base / f"{i:03}.json").read_text())["data"] for i in range(cfg["budget"])]
                sequences[method] = [(v["input_tokens"] + v["output_tokens"], v["response"]) for v in seq]
                totals[method] = sum(cost for cost, _ in sequences[method])
            cap = min(totals.values())
            for method, seq in sequences.items():
                used, prefix = 0, []
                for cost, response in seq:
                    if used + cost > cap:
                        break
                    used += cost
                    prefix.append(response)
                result = dataset.score(dataset.cases[oid], prefix)
                rows.append(dict(case_id=oid, seed=seed, method=method, token_cap=cap, tokens_used=used,
                                 attempts=len(prefix), R=result["recovery_rate"]))
    return {"rule":"Per paired case/seed use the smallest full 16-attempt token total among direct methods. "
                   "Score each consecutive prefix fitting that cap. Post-hoc resource sensitivity.",
            "methods":{m:{"R":mean(r["R"] for r in rows if r["method"] == m),
                           "mean_attempts":mean(r["attempts"] for r in rows if r["method"] == m)}
                       for m in methods}, "rows":rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--upstream", type=Path, default=ROOT / ".cache/hypospace")
    args = parser.parse_args()
    args.output.write_text(json.dumps(summarize(args.run, args.upstream), indent=2) + "\n")
