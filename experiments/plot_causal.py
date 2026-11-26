"""Plot official recovery under matched candidate budgets from the paired summary."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

LABELS = {"official": "Official history", "edge_count": "Edge count", "reachability": "Reachability",
          "feedback": "Error feedback", "structural_cycle": "Fixed rotation", "adaptive": "Adaptive",
          "action_llm": "Verified edits + Qwen", "action_uniform": "Verified edits + random"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("figure", type=Path)
    args = parser.parse_args()
    report = json.loads(args.summary.read_text())
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.15, 1]})
    groups = [list(LABELS)[:6], list(LABELS)[6:]]
    colors = ["#3d4856", "#887231", "#117d76", "#546cb6", "#925ba2", "#bc5431"]
    for ax, group, title in zip(axes, groups, ("Direct graph generation", "Verified graph-edit menu")):
        for i, name in enumerate(group):
            points = report["methods"][name]["R_at"]
            label = LABELS[name]
            ax.plot([int(k) for k in points], list(points.values()), marker=("o","s","^","D","x","v")[i],
                    color=colors[i], label=label, linewidth=1.8, markersize=5)
        ax.set_title(title, loc="left")
        ax.set_xticks([4, 8, 16])
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_xlabel("Candidate attempts")
        ax.grid(axis="y", alpha=.25)
        ax.spines[["right","top"]].set_visible(False)
        ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0,-.2), ncol=2)
    axes[0].set_ylabel("Mean official recovery")
    fig.suptitle(f'Four-node causal DAGs · {report["counts"]["n_cases"]} {report["split"]} cases', x=.07, ha="left")
    fig.subplots_adjust(left=.08, right=.98, top=.84, bottom=.32, wspace=.25)
    fig.savefig(args.figure, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
