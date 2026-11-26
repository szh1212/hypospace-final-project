# Qwen 3B 本地基线实验协议

## 研究任务与依据

课程文档第二项要求：提出新 ML 方法改善 LLM 在 HypoSpace 上的表现，提交公开 GitHub 仓库和 10 分钟小组视频，每位成员都参与讲解，按 novelty、importance、quality 评分。

本项目研究固定小模型下的假设生成策略，模型不训练或换大。选取官方 3D gravity-constrained voxel reconstruction 子任务：给出 3×3 二值俯视图，生成最多3层且下方有支撑的体素结构。按占用格数1/2/3分层，合法解数分别为3/9/27。这与正式论文第5.2节、表2的任务方向一致（论文第6.1节称变化为top-down views，而官方生成器实际按俯视图占用格数max_blocks分层；本项目以固定代码为准），但我们是小模型课程实验，不是复现论文所有模型和实验规模。

参考正式论文 https://proceedings.mlr.press/v306/chen26bz.html ，PDF共15页。第3节定义V/U/R，第5.2节定义投影和支撑约束，第6.5节已包含复杂度分层解码。注意第3节的 independent samples 描述与第5.2节、官方实现的历史条件生成存在差别：本项目明确复现官方代码的 history-conditioned baseline，不称为独立同分布采样。

官方代码固定 https://github.com/CTT-Pavilion/_HypoSpace 的 `c69e9318577b34b5b896996571aefd4ba6053f58`。不复制修改官方代码；通过 methods/szh-baseline-3d-task-b/experiments/bootstrap.py 拉取到忽略目录 .cache/hypospace。

## 模型与执行环境

- Qwen2.5-3B-Instruct，Ollama tag `qwen2.5:3b-instruct-q4_K_M`，量化 Q4_K_M。
- Ollama 0.40.18；模型 digest 和模板 SHA256 保存到 methods/szh-baseline-3d-task-b/experiments/model-lock.json，启动时核验。仅 tag 相同不够。
- 本机 http://localhost:11434，无 API Key，无商业 API、云端回退；运行费用0元（不含硬件、电力）。模型来自官方 Ollama registry。
- 基线硬件：Intel i5-1155G7，4核8线程，16GB RAM，Intel Iris Xe共享内存集显，无独立GPU；本次使用CPU推理。C/D/E属于同一512GB NVMe SSD；H是USB盘。
- 本机模型、Ollama二进制、虚拟环境和正式raw outputs均在 C:/Users/宋知恒/HypoSpaceLocal；仓库在H盘。其他队友自行选择本机SSD目录，不要照搬用户名或使用U盘环境。
- Python 3.12，requirements.txt固定核心依赖。Ollama服务只监听127.0.0.1，禁用云端，串行请求。

## 数据与采样配置

唯一配置源 methods/szh-baseline-3d-task-b/experiments/protocol.json；固定数据与划分 methods/szh-baseline-3d-task-b/experiments/manifest.json。正式协议已依据开发集冻结：Adapted Baseline为 adapted_baseline:transform，正式规模585次。冻结依据见baseline-freeze.json。

官方生成器穷举全部129个俯视观测。每层2个dev观测、5个test观测，分层随机打乱后确定ID；split seed=33550336。三层合计6个dev、15个test。dev用于设计和调参；test仅在方法冻结后评估。官方合法解仅提供给评测器，不能输入生成方法。

当前候选正式协议：repeat seeds=[17,42,2026]，temperature=0.7，top_p=0.9，top_k=40，repeat_penalty=1.0，max_tokens=512，num_ctx=8192，num_thread=4，num_gpu=0。固定system提示词见配置。逐次Ollama seed = (repeat_seed + SHA256(observation_id)前8位所表示的整数 + query_index) mod (2^31-1)，query_index从0开始。参数和随机数生成均明确锁定，但不同硬件/软件后端不保证逐字一致。

每题Q=|H|×query_multiplier，当前multiplier=1，因此分别3/9/27次；15题×3重复=585次调用。每次产生一个候选。官方 max_retries=1：不对解析失败重试，不额外修复、不丢掉无效或重复输出。HTTP失败立即中止，保留成功请求缓存，修复服务后原命令恢复。

smoke test 使用各层第一个dev观测、seed17、每题3次，共9次真实调用，覆盖三个规模且不触碰test。根据真实输出检查格式、物理约束、截断、运行速度；若模型表现差，保留结果并分析，不自动换模型或用模拟结果替代。

## 基线与评价口径

基线直接使用官方 Benchmark3D.evaluate_single_observation_set 的提示词、parser、hash、normalization和validator。每次下一条prompt包含此前全部解析成功且不重复的结构（官方 last-10 局部变量并未实际被用于截断）。因此单纯“把历史答案加入提示词避免重复”不是我们的新方法。

V=有效生成次数/请求次数；U=所有可解析结构的去重数量/请求次数，包含无效但不同的结构；R=去重后的有效且命中ground-truth集合的结构数/ground-truth集合大小。解析失败分母照计。末尾全零层在官方hash中归一化消除。主结果是各观测×重复的宏平均，并分占用格数报告均值/样本标准差。标准差不是独立样本置信区间；方法比较使用同观测同seed配对差值。

已确认的官方边界：validator不检查最大高度，parser会补齐不规则行。我们保留官方口径以便可比，额外报告 strict_valid_count（在解析后补充高度检查，不是严格的原始文本格式验证）。真正超出合法解空间的结构不会增加R。任何修改评测器都必须同时重跑所有方法，不得只为某个方法放宽条件。

在所有生成都落在合法解集、Q=|H|时，终点U和R可相等；因此同时报告k=1..Q的覆盖曲线。3D小任务可被精确非ML枚举解出，本项目只是受控的小模型策略实验，不能据此声称真实科学发现能力。

## 统一接口

- 模型：methods/szh-baseline-3d-task-b/src/ollama_client.py 的 OllamaClient(config).request(prompt,seed)、generate(request)，返回原文、input/output token、耗时和停止原因。禁止绕开接口隐藏额外模型调用。
- 数据：methods/szh-baseline-3d-task-b/src/experiment_api.py 的 load_dataset(split)，仅返回 observation_id/observation，不暴露解集。
- 评价：evaluate_outputs(observation_id, outputs)，将所有原始候选交给官方评测器。
- 策略：在src创建模块，定义 transform(prompt: str, context: dict) -> str；context只含observation、query_index、history。runner用 --method your_method:transform 加载。保持最终Layer输出格式一致，hook内部不进行模型调用或读取ground truth。
- 对比：methods/szh-baseline-3d-task-b/src/compare_runs.py，检查两次run的完整配置、模型指纹、split、逐题调用次数，输出配对V/U/R差值和调用、token、时间。

## 等预算规则

主表使用相同总生成调用预算，所有生成出来的候选都进入评测，包括被方法内部认为不合格、重复或应舍弃的候选，不能通过多生成再筛选增加优势。需要自我修正时，第一轮和修正轮各消耗一次预算，两轮原始候选都记录；通过history在下一次prompt内发出修正指令即可，不在hook里偷偷多调一次。非候选的规划调用也必须记入总资源与调用预算，不把它伪装成免费预处理；如果这种调用导致无法使用现有统一接口，先扩展共享runner与计数测试，再运行所有对照。

如展示更大调用预算的辅助实验，所有方法和baseline使用相同新预算重新运行，单列结果，不与585次版本混成主表。额外报告Token和总时间，因为相同调用次数不意味着相同算力。可再加等Token/等时间分析，但必须保存完整轨迹。所有测试设置在看test结果前锁定。

## 输出与恢复

identity.json记录完整配置、模型指纹、dataset SHA、split、方法源码SHA；raw/<seed>/<observation_id>/<query>.json记录请求、seed、prompt、response、usage、timing_ns、elapsed_s、done_reason、请求SHA。partial.json保存完成的观测；summary.json为schema_version=1，保存aggregate、by_blocks、results、curves、resource_totals、runner SHA和平台信息。

字段映射：valid_rate=V，novelty_rate=U，recovery_rate=R。逐题包含n_queries/n_valid/n_unique/n_recovered_gts、parse_success_rate、strict_valid_count、truncated_count、token_usage、latency_s。curves通过重放已保存的真实输出计算，不增加任何模型调用。resource_totals给出calls、input_tokens、output_tokens、model_call_seconds、truncated_outputs。

相同命令与输出目录可断点恢复；identity或prompt SHA不一致会拒绝混用缓存。新实验必须换目录。累计时间包括首次生成缓存记录的耗时，不能把恢复时的缓存读取时间报告为推理速度。

小型汇总和PNG/PDF图放docs；完整原始输出保存在本机SSD，不推送权重、虚拟环境或大型文件。正式基线完成后在README和experiment-log.md记录结果与精确命令。

## 队友方法方向

A：复杂度/高度分层策略可作为论文已有方法的对照，在此之上提出与本文不同且可验证的改进。
B：根据已生成候选的覆盖描述自适应选择下一次提示策略；若使用学习器或bandit，只在dev学习，明确状态、奖励与训练数据。
C：空间顺序/等价表示变换与一致性约束，输出必须变回原坐标的Layer格式；记录变换选择和消融，不能在评价时改变等价关系。

这些是待研究的方向，不是已验证的新算法。每人交方法动机、实现、dev消融、冻结参数、test结果、资源开销与局限；简单prompt启发式不能写成训练过的ML模型。正式论文已包含分层解码，必须明确相对已有工作的新增点。


## v3正式冻结与原始对照

Original Baseline：不传--method，完整保留官方prompt。既有真实9次dev结果见figures/smoke。Adapted Baseline：传--method adapted_baseline:transform；仅将任务说明改为清楚的行列/支撑关系、要求底层复制观测和简洁Layer输出，保留历史。初版在全部6个dev观测的18次生成V=1，U=1/3；历史语义修复后重新核验为15/18有效，以修复版作为最终共同基线；开发选择目标为有效率优先，再考察覆盖。该适配属于共同基线，不作为队友创新方法。

正式比较目标是改进方法相对Adapted Baseline的增益。原始dev成绩不能与正式test成绩直接作因果比较。dev研究中清晰说明、去除无关示例和简洁输出是组合变化，不能声称某一个词句独立造成全部改善；坐标附加、分步推理与固定底层方案也已实测，不一定优于组合提示。所有dev结果见dev-study.json，确切源码见dev_prompts.py。

队友应从冻结的适配提示开始实现transform：先调用 adapted_baseline.transform(prompt,context) 再增加自己的策略。runner会传入官方prompt，故必须主动复用该函数，不要误用原始prompt作共同基线。

正式运行发现官方normalize对全零结构传NumPy数组会崩溃。公共适配层仅在该分支转为tolist，保留全零结构的hash与无效判定；此修复统一用于所有方法。已有真实请求通过缓存重放恢复，不重新抽样丢弃失败。
