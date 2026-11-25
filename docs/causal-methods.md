# 从 main 开始的因果图实验

实验分支 kevin/causal-main 的第一个提交以本地 origin/main 的 2c24720 为唯一父提交。
先前从 3D 分支开展的因果图试验保存在 kevin/causal-subspace。
本实验沿用已下载的官方评测代码、模型权重和 Python 环境。

## 原仓库的基线证据

| Git 版本 | 已有材料 | 可作何种比较 |
| --- | --- | --- |
| main，2c24720 | 项目说明、指标定义、空实验日志 | 提供研究目标，缺少实测成绩 |
| szh/baseline-3d，b9c0145 | 3D 数据生成和评测脚本、开发摘要、正式 585 条原始输出与指标 | 同一体素重建任务的性能对照 |
| 本项目旧因果图分支，111841e | 四节点 DAG 的 960 次调用 | 诊断有效性瓶颈及比较开发题表现 |
| 本分支 | 从 main 新增的因果图实验 | 在相同因果图观测、模型、种子和预算下比较 |

3D 开发集同三题、种子 17、每题三次。官方提示 V/U/R 为 0% / 88.89% / 0%。
最终修复版提示使用清晰的层结构说明和规范化历史，V/U/R 为 66.67% / 33.33% / 4.94%。
初版适配曾在这三题达到 V=100%，其历史处理随后得到修正。
正式适配结果为 V/U/R 78.52% / 21.65% / 17.45%，共 585 次真实模型调用。
其原始 3D 提示没有对应的正式等预算结果。完整 3D 数据集可用固定生成器重建。
基线文件均可从仓库历史中读取，如 git show origin/szh/baseline-3d:docs/formal-baseline.md。

## 协议和方法

- Qwen2.5-3B-Instruct Q4_K_M，本地 Ollama 0.40.18，温度 0.7。
- 固定官方版本 c69e9318577b34b5b896996571aefd4ba6053f58，使用官方生成器、解析和评分。
- 四个有标签节点、最多四条边，一次或两次干预，每次干预指定精确可达节点集合。
- 每种策略每题每个种子输出 16 个候选，前缀为 4/8/16。每个失败和重复均计入分母。
- 开发沿用上一轮两题，种子 17。测试从上次未用 ID 中随机选 8 题，每种干预次数 4 题。
- 抽题仅限有 4 到 80 个兼容解的观测，排序后按 Python Random(102901).sample 抽取。
- 测试种子为 17、42，答案集仅用于评分和划定评测难度。各组读取相同题面。
- 新题按节点重命名合并得到 6 种结构，其中 2 种在旧开发和测试案例中均未出现。
- 提示与策略源码、协议和 ID 清单在模型运行前提交为 5ecccf9。
- official 使用官方提示及其可解析历史，edge_count 追加按可行边数下界轮转的约束。
- reachability 将题面改写为必须可达和禁止可达节点，去掉具体示例，保留最近四种图。
- feedback 在上述设置上报告上一张图遗漏或多出的可达关系。
- structural_cycle 用同样反馈和候选边，按顺序轮转包含或排除某条边的要求。
- adaptive 根据新增有效且符合要求的图分配尝试，失败后切换，每四次优先探索较少访问的条件。
- 结构约束使用至多两个候选边特征，每个特征产生一对互补条件，不同特征对应的子空间可重叠。
- action_llm 从观测构造一个起始图，验证局部加边、删边或反转，模型从含 KEEP 的菜单中选择。
- action_uniform 用均匀随机选择同一菜单生成规则下的动作。两个选择器的历史可导致后续菜单不同。
- 动作菜单至多四项，优先提供未见图；仅实际选出的图进入历史，每次选错编号计为失败。
- 动作系统保留选择前的符号验证、历史和回溯，其性能归因为模型与搜索程序的组合。
- 主要观察等候选预算的宏平均恢复率，同时列出有效率、唯一性、真实调用和 token。

## 复现

在仓库根目录运行，已有官方代码可以通过 --upstream 显式指定，默认路径为 .cache/hypospace。
环境需要 Python 3.12、NetworkX、NumPy、SciPy、requests 和 PyYAML，作图使用 matplotlib。
推理通过 127.0.0.1:11434 使用本地固定版本和摘要的 Qwen 服务。
新机器需从上文固定版本准备官方代码、模型和服务。

```sh
python -m unittest discover -s tests -v
python experiments/run_causal.py --split dev
python experiments/run_causal.py --split test
python experiments/run_causal.py --split test --replay
python experiments/summarize_causal.py --input runs/main-test/summary.json --output docs/causal-test.json
```

每个原始请求、响应、种子、token、耗时及校验值保存在 runs/main-{dev,test}/raw。
traces 同时保存动作解码、解析结果对应的有效性、分支激活及菜单大小。
重新运行同一版本可续跑，--replay 逐项核对官方指标且不调用模型。
