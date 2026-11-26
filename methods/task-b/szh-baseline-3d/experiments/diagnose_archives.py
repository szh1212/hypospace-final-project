"""Describe failure modes from verified raw archives using the official parse/normalization."""
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".git").exists())
sys.path.insert(0, str(ROOT / "src"))
from hypospace_runner import upstream


def diagnose(folder, bench, observations):
    counts = Counter()
    with gzip.open(folder / "raw.jsonl.gz", "rt", encoding="utf-8") as archive:
        for line in archive:
            entry = json.loads(line)
            oid = Path(entry["path"]).parent.name
            raw = json.loads(entry["utf8"])
            counts["all"] += 1
            structure = bench.parse_llm_response(raw["response"])
            if structure is None:
                counts["parse_failure"] += 1
                continue
            structure = structure.normalize()
            obs = observations[oid]
            view = structure.get_top_view()
            target = bench._parse_observation(obs)
            projected = np.array_equal(view, target)
            supported = all(not np.any((upper == 1) & (lower != 1))
                            for lower,upper in zip(structure.layers, structure.layers[1:]))
            if not projected:
                counts["projection_mismatch"] += 1
                if np.array_equal(view, [[1,0,1],[0,0,0],[1,0,1]]):
                    counts["four_corner_projection"] += 1
            elif not supported:
                counts["support_only"] += 1
            else:
                counts["valid"] += 1
            if bench.validate_structure_matches_observations(structure,obs) != (projected and supported):
                raise ValueError(f"Failure classification disagrees with official validator: {oid}")
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
    if counts["all"] != 585 or counts["valid"] != sum(r["n_valid"] for r in metrics["results"]):
        raise ValueError("Classification count mismatch")
    return counts


def main():
    bench = upstream()[0].Benchmark3D(str(ROOT / "data/3d.json"))
    observations = {o["observation_id"]:o["observation"] for o in bench.all_observation_sets}
    docs = ROOT / "docs"
    lines = ["# 正式输出的失败分类", "",
             "每个方法以全部 585 个响应为分母。按官方验证顺序，先检查投影，再检查上层支撑。投影错误可能同时存在支撑问题。",
             "", "|类别（次数）|Original|Adapted|", "|---|---:|---:|"]
    counts = [diagnose(docs / "figures" / folder,bench,observations) for folder in ("original","baseline")]
    for key,label in (("parse_failure","无法解析"),("projection_mismatch","俯视图不符"),
                      ("support_only","俯视图正确但缺少支撑"),("valid","通过官方验证，含重复"),
                      ("four_corner_projection","其中，错误俯视图恰为示例的四角图案")):
        lines.append(f"|{label}|{counts[0][key]}|{counts[1][key]}|")
    lines += ["", "前四行互斥，最后一行是投影不符的子集。四角均被占用的投影不可能匹配本测试集的 1–3 个占用格；该计数描述输出中的图案，不能单独证明示例导致了错误。合法输出中的重复情况见两组 metrics.json 的 failure_categories。", "",
              "复现命令为 `python methods/task-b/szh-baseline-3d/experiments/diagnose_archives.py`。脚本从仓库中两个 gzip 原始归档读取响应，仅做离线回放。"]
    (docs / "formal-failures.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
