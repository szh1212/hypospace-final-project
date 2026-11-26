# 可验证性清单（分层生成策略路线）

所有结果都由冻结的本地运行目录和原始响应支撑；每一步都可以在无网络、无模型调用的
情况下离线复核。复核只用 `docs/`、`experiments/`、`runs/`（本地忽略目录）和
`.cache/hypospace`（官方固定提交 `c69e931`）。

## 环境

- Python 3.12，依赖 `networkx`、`numpy`；模型 `qwen2.5:3b-instruct-q4_K_M`，
  digest `357c53f…e4b`，Ollama `0.40.18`，采样参数冻结在 `src/causal_benchmark.py`。
- 官方上游必须是 `.cache/hypospace` 的固定提交 `c69e931`，`causal/` 源码树干净，
  否则 `Dataset` 拒绝加载。

## 单元测试

```bash
python3 -m unittest discover -s tests          # 43 项，含分层划分、强制边、两级分层、并集、预算强制与有效性过滤
```

覆盖性质：每个真解恰好属于一个先验分层；强制边出现在每个真解中；预算强制只丢弃
超出边数上限的后补边、永不丢弃固定边；`enforce_limit` 对未超限并集是恒等。

## 离线逐调用审计

```bash
# parent-strata v1（开发 256 次 + 测试 1,664 次真实调用）
python3 experiments/analyze_parent_strata.py --split dev
python3 experiments/analyze_parent_strata.py --split test

# skeleton_complete（测试 416 次真实调用；对照为 v1 冻结单元）
python3 experiments/analyze_parent_skeleton.py --split test \
  --protocol experiments/parent-skeleton.json \
  --folder runs/skeleton-test \
  --extra-folder runs/skeleton-dev --extra-protocol experiments/parent-skeleton-dev.json \
  --out docs/parent-skeleton-test.json

# skeleton_complete_forced / skeleton_complete_limit（测试 832 次真实调用；
# 对照为 v1 四方法 + skeleton_complete）
python3 experiments/analyze_parent_skeleton.py --split test \
  --protocol experiments/parent-skeleton-forced.json \
  --folder runs/skeleton-forced-test \
  --extra-folder runs/skeleton-test --extra-protocol experiments/parent-skeleton.json \
  --out docs/parent-skeleton-forced-test.json

# SZH 预算对齐（每题 13 次、种子 17/42/2026；对照重放到第 13 次调用）
python3 experiments/run_parent_skeleton.py --split test \
  --protocol experiments/parent-skeleton-aligned.json --out runs/skeleton-aligned-test --replay
python3 experiments/analyze_aligned_budget.py

# 第四代：两级分层 + 有效性过滤（V/U/R 三指标配对）
python3 experiments/run_parent_skeleton.py --split dev \
  --protocol experiments/parent-skeleton-valid-dev.json --out runs/skeleton-valid-dev --replay
python3 experiments/run_parent_skeleton.py --split test \
  --protocol experiments/parent-skeleton-valid.json --out runs/skeleton-valid-test --replay
python3 experiments/analyze_valid_methods.py
```

每条审计都从 `runs/*/raw/` 重放：请求摘要（prompt+seed+method）、分层轮转是否出现在
实际提示中、共享题面前缀、固定边并集、被丢弃的指向锚点的边、预算强制、前缀 V/U/R
与汇总一致，并用 networkx 独立核对可达性与真解成员关系。

## 运行级重放

```bash
python3 experiments/run_parent_strata.py --split dev --replay   # 逐单元比对记录
python3 experiments/run_parent_strata.py --split test --replay
python3 experiments/run_parent_skeleton.py --split dev --protocol experiments/parent-skeleton-dev.json \
  --out runs/skeleton-dev --replay
python3 experiments/run_parent_skeleton.py --split test --protocol experiments/parent-skeleton.json \
  --out runs/skeleton-test --replay
python3 experiments/run_parent_skeleton.py --split test --protocol experiments/parent-skeleton-forced.json \
  --out runs/skeleton-forced-test --replay
python3 experiments/run_parent_skeleton.py --split dev --protocol experiments/parent-skeleton-forced-dev.json \
  --out runs/skeleton-forced-dev --replay
```

parent-strata v1 的重放以其冻结生成提交为准（identity 里记录的提交）；骨架家族的四个运行目录
在最终提交处从原始响应重建，重放在当前 HEAD 通过。每次运行的 `identity.json` 记录模型指纹、
上游与数据集 SHA、协议 SHA、源码 SHA 和生成时 Git 提交；协议与代码在推断开始前冻结并提交
（`8786caa`、`c14245e` 及最终提交）。原始响应不可用时运行会直接报错，不会被静默模拟。

## 统计口径

- 主指标：每题先对两个种子平均 R@16，再对 13 个测试题等权平均（macro）。
- 配对差：同题同种子同预算下方法与对照的 R 差，按题平均后对 13 题重抽样
  10,000 次取 2.5%/97.5% 分位数（bootstrap 百分位区间），种子 33550336 固定。
- 预算点：4 / 8 / 16 次调用的前缀分数由同一批原始响应重放得到。
