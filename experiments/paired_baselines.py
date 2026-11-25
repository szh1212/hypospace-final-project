"""Rebuild the matched comparison from the two exported metrics files (no inference)."""
import json
from pathlib import Path
from statistics import mean
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs/figures"
NAMES = ("Original", "Adapted")
METRICS = ("valid_rate", "novelty_rate", "recovery_rate")
COLORS = ("#805420", "#166b91")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    runs = [read(FIG / folder / "metrics.json") for folder in ("original", "baseline")]
    manifest = read(ROOT / "experiments/manifest.json")
    cfg = read(ROOT / "experiments/protocol.json")
    keys = {(s, oid) for s in cfg["repeat_seeds"] for oid in manifest["splits"]["test"]}
    if len(keys) != 45:
        raise ValueError("Expected 15 observations and 3 repeat seeds")
    groups = []
    for run, method in zip(runs, ("official-history", "adapted_baseline:transform")):
        identity = run["identity"]
        if (identity["config"] != cfg or identity["mode"] != "llm" or identity["smoke"]
                or identity["method"] != method or identity["split"] != "test"
                or identity["dataset_sha256"] != manifest["dataset_sha256"]
                or identity["model_fingerprint"] != runs[0]["identity"]["model_fingerprint"]):
            raise ValueError("Protocol or model mismatch")
        rows = run["results"]
        if (len(rows) != len(keys) or {(r["seed"],r["observation_set_id"]) for r in rows} != keys
                or any(r["n_queries"] != r["n_ground_truths"] or r["n_queries"] != 3**r["blocks"] for r in rows)
                or sum(r["n_queries"] for r in rows) != run["completed_calls"] or run["completed_calls"] != 585):
            raise ValueError("Incomplete or unequal task budgets")
        groups.append([[mean(r[m] for r in rows if level == 0 or r["blocks"] == level)
                        for m in METRICS] for level in (1, 2, 3, 0)])
    out = FIG / "comparison"
    out.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained", sharey=True)
    for j,(ax,title) in enumerate(zip(axes, ("Validity", "Uniqueness", "Recovery"))):
        for i,name in enumerate(NAMES):
            ax.bar([x+(i-.5)*.36 for x in range(4)], [g[j] for g in groups[i]],
                   width=.36, label=name, color=COLORS[i])
        ax.set(title=title, xticks=range(4), xticklabels=["L1","L2","L3","Overall"], ylim=(0,1))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set_ylabel("Macro mean")
    axes[-1].legend()
    fig.savefig(out / "metrics.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained", sharey=True)
    for level,ax in enumerate(axes, 1):
        for i,run in enumerate(runs):
            curve = [0.]
            for k in range(1,3**level+1):
                points = [p["recovery_rate"] for p in run["curves"] if p["k"] == k and p["blocks"] == level]
                if len(points) != 15:
                    raise ValueError("Missing prefix scores")
                curve.append(mean(points))
            if abs(curve[-1]-groups[i][level-1][2]) > 1e-12:
                raise ValueError("Curve endpoint mismatch")
            ax.plot(range(len(curve)), curve, label=NAMES[i], color=COLORS[i], marker="." )
        ax.set(title=f"Level {level}  /  |H| = {3**level}", xlabel="Calls per observation", ylim=(0,1))
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.grid(alpha=.2)
    axes[0].set_ylabel("Mean ground-truth coverage R@k")
    axes[-1].legend()
    fig.savefig(out / "coverage.png", dpi=180)
    plt.close(fig)
    lines = ["# Original and Adapted on the frozen test split", "",
             "|Level|Calls per method|Original V|Original U|Original R|Adapted V|Adapted U|Adapted R|",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for idx,(label,n) in enumerate(zip(("1","2","3","Overall"), (45,135,405,585))):
        scores = [f"{v:.2%}" for group in groups for v in group[idx]]
        lines.append("|"+"|".join([label,str(n),*scores])+"|")
    lines += ["", "![V/U/R by difficulty](figures/comparison/metrics.png)", "",
              "![Coverage by call](figures/comparison/coverage.png)", "",
              "Each difficulty averages five observations and three seeds. Overall gives equal weight to the 45 observation–seed pairs. Each prefix uses the original proposal order.", ""]
    for name,run in zip(NAMES,runs):
        res = run["resource_totals"]
        lines.append(f"- {name}: {res['calls']} calls, {res['input_tokens']:,} input and {res['output_tokens']:,} output tokens, {res['model_call_seconds']:.1f} summed request seconds, {res['truncated_outputs']} length-limited responses. Outcomes: {run['failure_categories']}.")
    lines += ["", "[Formal failure analysis](formal-failures.md) · [Protocol audit and reproduction](baseline-audit.md) · [Team instructions](team-message.txt)"]
    (ROOT / "docs/paired-results.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
