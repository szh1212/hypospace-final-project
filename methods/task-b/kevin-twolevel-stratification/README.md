# Kevin two-level stratification — Task B (3D Voxel Reconstruction)

Algorithm: `src/strata_3d.py`（分层/提示/修复纯逻辑）+ `src/hypospace_runner_3d.py`（钉住官方评测器的可审计运行器）。冻结推理配置与官方评测器口径与 `../szh-baseline-3d/` 一致：同数据集（sha256 `61cebef…`）、同 15 题测试集与 3 种子（17/42/2026）、同预算（每题 3^b 次调用，共 585 次）、同模型与采样参数（qwen2.5:3b-instruct-q4_K_M，Ollama 0.40.18）、同一请求种子公式。**仅方法不同**；与基线的比较全部在相同 (题, 种子, 预算) 上配对。

## 方法（四代演进，最终 = 两级分层 + 有效性过滤）

1. **口头分层** `verbal`：提示中口头要求 (k2,k3) 层块数，无系统强制。
2. **骨架强制** `free`：Layer 1 = 俯视图由系统固定，S3⊆S2 修复。
3. **单级分层** `k2`：钉住 |S2|=k2 + 系统修复。
4. **两级分层 + 有效性过滤** `joint`（最终）：第一级钉住 (k2,k3)=(|S2|,|S3|)，层间互斥；
   第二级在每个查询内由系统强制锚点列的成员关系（∈/∉S2、∈/∉S3），层内锚点三元组
   轮转，补全顺序按锚点轮换；模型输出按"最接近原始输出的层内合法结构"确定性修复，
   解析失败回退到锚定层内的顺序最小结构。

分层完全先验：不读任何已恢复解（提示中的 prior outputs 只列已输出结果防重复，与
基线同机制）、不改官方表示（层列表输出 + 确定性修复）、不做动作选择或回溯搜索。

## 正式结果（15 题 × 3 种子 × 3^b 调用；宏观均值，配对 bootstrap 10,000 次）

| 方法 | V | U | R | 调用 |
| --- | ---: | ---: | ---: | ---: |
| SZH 基线（冻结数据） | 78.52% | 21.65% | 17.45% | 585 |
| **Kevin 两级分层 + 有效性过滤** | **100.00%** | **95.97%** | **95.97%** | 585 |

配对差（最终 − SZH 基线）：ΔV **+21.48pp** CI95 [+10.37, +34.07]；ΔU **+74.32pp**
CI95 [+69.79, +78.52]（45/45 单元全胜）；ΔR **+78.52pp** CI95 [+74.16, +82.72]
（45/45 单元全胜）。三项指标的配对置信区间均高于零。

完整报告、逐题表与四代演进见 [docs/experiment-results-3d.md](docs/experiment-results-3d.md)；
与基线的对比数据速览见 [docs/experiment-results.md](docs/experiment-results.md)；
汇总数据见 [reports/metrics.json](reports/metrics.json)。

## 复现

```sh
cd methods/task-b/kevin-twolevel-stratification
python3 src/hypospace_runner_3d.py --prepare                 # 生成数据集并校验 sha
PYTHONPATH=src python3 -m unittest discover -s tests          # 单元测试
PYTHONPATH=src python3 src/hypospace_runner_3d.py --gen joint --mode llm --split test --out runs/joint-test
PYTHONPATH=src python3 experiments/audit_3d.py runs/<run>     # 逐调用离线审计
PYTHONPATH=src python3 experiments/analyze_3d.py --baseline ../../szh-baseline-3d/adapted/reports/metrics.json
```

## 可验证性与披露

- 协议与代码在推断前冻结（运行目录 `runs/*/identity.json` 记录协议与方法源码 sha256）；
  原始调用与响应**不入库**（按仓库约定），`reports/raw-manifest.json` 保留全部 2,145 个
  原始记录的 SHA256 清单。
- `experiments/audit_3d.py` 从原始记录重放每一通调用（提示、分层/锚点、请求 sha256、
  过滤结果、官方 V/U/R 与曲线），8 个运行共 12,156 项检查全部通过。
- 布局迁移：方法最初在旧仓库布局的 `3d/` 下冻结并推断；迁入 `methods/` 布局时仅将基准
  检出路径改为向上查找（纯路径接线，方法逻辑逐字节不变），单元测试与全部审计已从新
  位置重放通过。
- 测试题与 SZH 基线共用（配对比较所需，同其"非严格 unseen"披露一致），未依据测试结果
  调整方法或采样超参。
