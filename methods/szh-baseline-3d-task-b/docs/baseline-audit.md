# 两条正式基线的协议核查

**Original** 复用固定上游版本的 `Benchmark3D.create_prompt` 和历史迭代逻辑。**Adapted** 固定为 `methods/szh-baseline-3d-task-b/src/adapted_baseline.py:transform`，是三个改进方法的共同比较对象。两者共用本地 Ollama 传输、系统消息、采样参数、逐次种子、数据、评价及失败处理。Original 对照的是同一 Qwen 模型上的官方用户提示词。论文表 2 使用另外七个模型及不同推理服务，没有该 Qwen 量化模型的参考成绩。[论文 §§3、5.2、6.1 与表 2](https://proceedings.mlr.press/v306/chen26bz.html) · [固定上游代码](https://github.com/CTT-Pavilion/_HypoSpace/blob/c69e9318577b34b5b896996571aefd4ba6053f58/3d/run_3d_benchmark.py)

## Adapted 改了什么

- 两个版本都展示二维俯视矩阵。Adapted 从相同九位观测按行展开为三行，明确行从上往下、列从左往右，区分平面行与高度层。
- 正上方投影表示同列任意高度有块；每个块都要由正下方支撑。两条规则合起来，底层必然等于俯视图。Adapted 将这条推论直接写出来，明确上层是下层子集，零格各层均为零。具体高度仍由模型提出。
- Adapted 移除固定四角结构示例及长篇说明，改为三行二值数字的 Layer 占位模板，要求仅输出结构，允许省略未用的上层。模板展示两层，可能影响模型偏好的层数。
- 两组都携带本题本次重复中此前可解析、归一化、按官方体素哈希首次出现的结构，包括无效的结构。Adapted 从自己的历史响应重建该列表，在提示词末尾展示，省去 Attempt 编号。不同方法的历史随各自输出自然分化。
- 生成接口中的数据只有观测、轮次和自身历史。Adapted 源码不读兼容解、标准高度或评分反馈。枚举真解由 evaluator 在比较恢复哈希时使用。这里对比的是整组提示词改变，正式两组数据无法单独归因到某一句话。[适配源码](../src/adapted_baseline.py) · [开发消融](dev-analysis.md)

## 分母与权重

对每个观测和重复，Q 包括无效、重复及解析失败的全部调用。V 为通过官方验证的提案次数 / Q，重复合法项仍计数。U 为可解析的不同归一化结构数 / Q，其中可以有无效项。R 为命中枚举真解的不同结构数 / 真解总数。R@k 只回放前 k 次输出，分母始终是该题全部真解数。不同种子各自重置历史；每题不能把三个种子的发现合并后再报告 R。

论文表 2 将难度标为 tp=1/2/3，第 6.1 节描述为 top-down views。固定生成器每题输入一张图；本项目的 Level 按图中 **占用格数** 1/2/3 定义。高度上限 3，每个占用格独立取高度 1–3。各级候选观测池分别为 C(9,1)=9、C(9,2)=36、C(9,3)=84；各抽 2 个 dev 和另外 5 个 test。每级 5 个测试观测 × 3 个种子，共 15 条题目–重复记录。每条的 Q=|H|=3/9/27，对应 45/135/405 次调用。总体宏平均赋予 45 条记录同等权重，也等于三个难度均值的算术平均。不要用全部 585 次的合并比例替代它。metrics.json 的 std 为记录间样本标准差，包含同题多次重复，不是 45 个独立观测的标准误。

论文 §3 与 §6.1 通常取 N=|H|，分难度对实例取均值并报告离散程度。文字提到独立采样，3D 官方实现逐轮带历史，本项目遵循后者。论文表 2 没有给出本项目固定的 15 个测试 ID 或三个种子。论文 §6.6 的温度、top-p 与预算扫描属于 Boolean Genetic Interaction。此处固定 temperature=0.7、top_p=0.9、top_k=40、max_tokens=512、num_ctx=8192、repeat_penalty=1，三组 repeat_seed 为 17/42/2026；完整运行身份以配置与模型锁为准。[冻结参数](../experiments/protocol.json) · [划分](../experiments/manifest.json) · [模型锁](../experiments/model-lock.json)

固定上游 3D CLI 的默认值是 n_samples=10、seed=None、query_multiplier=1、max_retries=3，温度配置缺省时取 0.7。课程实验保留预算倍率和温度缺省值，改用 manifest 指定观测、显式种子、max_retries=1。这里 1 表示每个提案仅尝试一次，解析失败占用原预算。CLI 默认值不能当作论文表 2 的实测参数。

两个版本共用同一个全零结构归一化兼容修复，避免 NumPy 数组导致异常，并保留该输出。V 采用上游 parser / validator 的实际宽容规则；独立记录的 strict_valid_count 增加高度检查，不用于正式 V。Adapted 在之前一次中止的测试运行中发现了历史处理缺陷，修复后重新在开发集验证，再完成冻结的 585 次实验；该修复接触过部分测试输出。[冻结记录](baseline-freeze.json)

## 复现与核查

先按 [本地环境说明](local-setup.md) 安装模型及依赖，并准备数据。在仓库根目录运行以下 PowerShell 命令，`$runs` 可替换为本机 SSD 路径。已有 Adapted 结果可直接从仓库读取，只需重绘时执行最后一行。

```powershell
$runs = Join-Path $env:USERPROFILE 'HypoSpaceLocal/runs'
python methods/szh-baseline-3d-task-b/src/hypospace_runner.py --out "$runs/original-formal-v4"
python methods/szh-baseline-3d-task-b/src/hypospace_runner.py --method adapted_baseline:transform --out "$runs/adapted-formal-v4"
python methods/szh-baseline-3d-task-b/src/export_run.py "$runs/original-formal-v4" --out methods/szh-baseline-3d-task-b/original/reports
python methods/szh-baseline-3d-task-b/experiments/verify_archive.py "$runs/original-formal-v4" methods/szh-baseline-3d-task-b/original/reports
python methods/szh-baseline-3d-task-b/experiments/verify_archive.py "$runs/adapted-formal-v4" methods/szh-baseline-3d-task-b/adapted/reports
python methods/szh-baseline-3d-task-b/experiments/paired_baselines.py
```

每组 `raw.jsonl.gz` 的每一行包含相对路径 path 和原始文件全文 utf8。按 UTF-8 编码该字符串即得到 raw-manifest.json 所列 SHA256 对应的确切字节，包括请求、响应、用量与耗时。核查脚本从官方提示词或冻结的适配函数重建每次请求，用历史输出离线回放并核对每题 V/U/R，无额外推理调用。
