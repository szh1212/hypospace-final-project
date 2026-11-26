# 自适应覆盖引导（coverage_guided）：test 正式结果

**预注册判定：未达标。** 主指标 Recovery 提升 +4.44pp，低于预注册的 +5pp 阈值；
护栏 Validity −0.66pp 在 −2pp 容差内。按预注册写好的规则，如实报告为"方向成立、效应量小于预期"，
不追加事后解释去凑阈值。

## 方法（相对基线的唯一增量）

兼容结构集合由观测完全决定（k 个占用格 → 3^k），所以 Recovery 的失败不是"生成不出合法结构"，
而是"反复生成已经出现过的合法结构"。Adapted 基线已经做了历史去重并提示"不要重复"，
但从未指出**搜索在哪个维度上一直是窄的**。

本方法在 `adapted_baseline.transform` 之后追加一段维度级搜索报告：

- 当前已找到多少兼容结构（k/n）
- 每个占用格实际用过哪些高度
- 指令：只改"只试过一种高度"的格子

**不给任何尚未出现的结构**，模型仍需自己构造答案。这是本方法与"直接枚举 3^k"的分界线。

代码：`methods/jcj-coverage-guided-task-b/src/coverage_guided.py`。纯函数，无模块级可变状态，不读取 `data/`、`experiments/` 或 ground truth。

## 总体结果（45 个 observation×seed 配对）

| 指标 | Adapted 基线 | 本方法 | 配对差 Δ | 95% CI | p |
|---|---:|---:|---:|---|---:|
| Validity | 78.52% | 77.86% | −0.66pp | [−4.64, +3.33] | 0.741 |
| Uniqueness | 21.65% | 25.27% | +3.62pp | [−0.29, +7.53] | 0.069 |
| **Recovery** | **17.45%** | **21.89%** | **+4.44pp** | **[+0.14, +8.74]** | **0.043** |

配对差的标准差为 13.3 / 13.0 / 14.3pp，说明逐题波动远大于平均效应——
这也是为什么必须用配对比较而不是两组独立均值。

## 分层结果

| Level | V 基线→本方法 | U 基线→本方法 | R 基线→本方法 | R 变化 |
|---|---|---|---|---:|
| 1（3 候选） | 95.56 → 100.00 | 42.22 → 48.89 | 37.78 → 48.89 | **+11.11pp** |
| 2（9 候选） | 60.00 → 50.37 | 17.04 → 20.74 | 10.37 → 11.85 | +1.48pp |
| 3（27 候选） | 80.00 → 83.21 | 5.68 → 6.17 | 4.20 → 4.94 | +0.74pp |

## 失败分类（全部 585 次，含失败和重复）

| 类别 | 基线 | 本方法 |
|---|---:|---:|
| parse failure | 1 | 0 |
| invalid structure | 136 | 135 |
| valid duplicate | 400 | 392 |
| new valid | 48 | 58 |

"new valid" 从 48 升到 58，重复从 400 降到 392。注意这是池化计数，
上表的百分比是逐题平均，两者不能直接换算。

## 资源

| | 基线 | 本方法 |
|---|---:|---:|
| 调用数 | 585 | 585 |
| 输入 tokens | 178,307 | 223,990（+25.6%） |
| 输出 tokens | 28,776 | 26,383 |
| 截断输出 | 0 | 0 |
| 请求累计耗时 | 3,275.1s | 1,959.8s |

耗时差异主要来自硬件不同（基线在另一台 CPU 机器上跑），**不作为效率比较的依据**。
输入 token 增加来自追加的搜索报告，属预期成本。

## 需要写进论文的三个观察

1. **效应集中在 L1。** 3 个候选、3 次机会时，R 从 37.78% 提到 48.89%。
   这说明"告诉模型它一直在哪一维重复"确实起作用。但 L1 的上限是 100%，
   本方法只走到一半，机制没有完全生效。

2. **L2 的 Validity 掉了 9.63pp**（60.00 → 50.37）。两个占用格时报告变长，
   且"必须改变某一格高度"的指令可能把模型逼向不满足支撑/投影的组合。
   这是本方法目前最需要解释的副作用，**没有做消融定位原因**，只能作为已知局限报告。

3. **L3 几乎不动，且指令基本被忽略。** 任务结束时仍有 **89% 的占用格从未被改变过高度**
   （L2 为 80%，L1 为 53%）。27 次调用、历史累积到二十多个结构之后，
   模型对尾部指令的敏感度急剧下降。这是下一步最该攻的点，而不是继续调措辞。

## 局限

- 单模型（Qwen2.5-3B Q4_K_M）、单任务、15 个 test 观测，3 个 seed 共享同一批观测。
- test 只跑一次，没有第二次重复来估计 run-to-run 方差。
- L2 的 Validity 下降没有独立消融，机制归因不完整。
- 覆盖率只统计通过官方 validator 的提案，与基线展示给模型的历史范围（含非法结构）不一致；
  这是有意为之（非法结构对 Recovery 贡献为 0），但需要写进 limitation。
- 未做 dev 消融（`transform_stats_only` / `transform_cells_only`），因此无法区分
  "覆盖计数"和"格级方向"各自的贡献。

## 精确命令

```powershell
$Py = "D:\HypoSpaceLocal\.venv\Scripts\python.exe"
$Repo = "D:\HypoSpace\hypospace-final-project"
Set-Location $Repo
$Run = "D:\HypoSpaceLocal\runs\cg-test-v1"

& $Py methods/szh-baseline-3d-task-b/src/hypospace_runner.py --method coverage_guided:transform --out $Run
& $Py methods/jcj-coverage-guided-task-b/experiments/validate_coverage.py $Run
& $Py methods/szh-baseline-3d-task-b/src/export_run.py $Run --out methods/jcj-coverage-guided-task-b/reports
& $Py methods/szh-baseline-3d-task-b/src/plot_results.py "$Run\summary.json" --out methods/jcj-coverage-guided-task-b/reports
& $Py methods/szh-baseline-3d-task-b/src/compare_runs.py methods/szh-baseline-3d-task-b/adapted/reports/metrics.json "$Run\summary.json" --out methods/jcj-coverage-guided-task-b/docs/cg-comparison.json
```

## 可复核性

- `methods/jcj-coverage-guided-task-b/experiments/validate_coverage.py` 用官方 parser 重放了全部 585 条 raw 响应，
  逐题重算的 valid rate 和 recovery rate 与 evaluator 报告的值完全一致（`OK`）。
  这证明钩子里的高度向量记账与官方评分口径一致，模型看到的搜索报告是真实的。
- 原始响应保留在本机 SSD `cg-test-v1/raw/`，`methods/jcj-coverage-guided-task-b/reports/raw-manifest.json` 是逐文件 SHA256。
- 配对比较已通过 `compare_runs.py` 的可比性检查（config / model_fingerprint / split /
  dataset_sha256 / smoke 全部一致，且每个任务的 n_queries 相等）。
