"""Export and document a completed formal run. Never creates results before completion."""
import json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run=Path.home()/'HypoSpaceLocal/runs/adapted-formal-v4'
d=json.loads((run/'summary.json').read_text(encoding='utf-8'))
assert d['completed_calls']==585 and d['identity']['method']=='adapted_baseline:transform'
for script,args in [('export_run.py',[str(run),'--out',str(ROOT/'docs/figures/baseline')]),('plot_results.py',[str(run/'summary.json'),'--out',str(ROOT/'docs/figures/baseline')])]:
 subprocess.run([sys.executable,str(ROOT/'src'/script),*args],check=True)
v=d['aggregate'];res=d['resource_totals']
report=f"""# Formal Adapted Baseline result

585/585 real local Qwen calls completed. Model, sampling and data IDs were frozen using development data. A history implementation defect discovered in an aborted partial test run was repaired, rechecked on dev, and the complete 585-call run was restarted. No sampling hyperparameters were tuned on test, but test was not strictly unseen for this repair. Original official prompt remains available without --method. Adapted Baseline uses adapted_baseline:transform; teammate methods start from this same prompt.

Macro V={v['valid_rate']['mean']:.6f}, U={v['novelty_rate']['mean']:.6f}, R={v['recovery_rate']['mean']:.6f}.
Calls={res['calls']}; input tokens={res['input_tokens']}; output tokens={res['output_tokens']}; summed inference wall time={res['model_call_seconds']:.3f} seconds; truncated outputs={res['truncated_outputs']}. Cost=0 commercial API fees.

Full aggregate/sample SD, per-stratum results, task records and curves: figures/baseline/metrics.json. Raw output checksums: figures/baseline/raw-manifest.json. Full prompts, model responses and timings remain on SSD at HypoSpaceLocal/runs/adapted-formal-v4/raw. No outputs were replaced by simulated answers. Figures show all official scoring outcomes, including invalid and duplicate outputs.

Reproduce: python src/hypospace_runner.py --method adapted_baseline:transform --out <SSD>/runs/adapted-formal-v4
Export: python experiments/finalize_baseline.py (owner's default local path; otherwise use export_run.py and plot_results.py directly).

The adapted prompt improves task readability but is not a claimed novel algorithm. Small dev/test samples and prompt-based generation limit generalization. Development Original Baseline metrics and formal Adapted metrics use different observation/budget settings and must not be interpreted as a controlled test-set improvement estimate. The matched dev comparisons are in dev-study.json.
"""
(ROOT/'docs/formal-baseline.md').write_text(report,encoding='utf-8')
(ROOT/'README.md').write_text('# HypoSpace Qwen 3B Final Project\n\n**Formal Adapted Baseline complete: 585 real local calls, zero paid API usage.**\n\n'+report.split('\n',2)[2]+'\n\n![Formal coverage](docs/figures/baseline/curves.png)\n\n[Local setup](docs/local-setup.md) · [Protocol](docs/baseline-protocol.md) · [Development diagnosis](docs/dev-analysis.md) · [Team handoff](docs/team-message.txt)\n',encoding='utf-8')
p=ROOT/'docs/experiment-log.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n'+report,encoding='utf-8')
(ROOT/'docs/project-plan.md').write_text('# Team status\n\nBaseline owner: local deployment, evaluator verification, dev ablations, frozen configuration and formal 585-call Adapted Baseline complete. Three teammates now develop improvements using the shared model/data/evaluator and equal generation budget. Original official prompt remains available for additional controls.\n',encoding='utf-8')
(ROOT/'docs/team-message.txt').write_text(f"""基线已跑完并上传到 szh/baseline-3d 分支：正式585次真实本地调用，V={v['valid_rate']['mean']:.4f}、U={v['novelty_rate']['mean']:.4f}、R={v['recovery_rate']['mean']:.4f}。下面可以直接喂给各自AI：

请在EEC4300 HypoSpace项目中实现我负责的【改进方法】。先执行 git clone -b szh/baseline-3d https://github.com/szh1212/hypospace-final-project.git，进入仓库后 git switch -c 我的名字/方法名。阅读README、docs/local-setup.md、baseline-protocol.md、dev-analysis.md、formal-baseline.md及experiments下protocol.json、manifest.json、model-lock.json。

严格零预算，模型固定Qwen2.5-3B-Instruct Q4_K_M、Ollama0.40.18，本机localhost:11434，不要API Key、不要云端回退或换模型。模型权重和Python3.12虚拟环境放本机SSD，按local-setup安装依赖并核对digest。官方原prompt保留为Original Baseline；本次共同基线是开发集选定的Adapted Baseline，不能将适配prompt当作自己的创新。

src/ollama_client.py提供模型接口，experiment_api.load_dataset/evaluate_outputs提供数据和评价。src下定义transform(prompt,context)，先调用adapted_baseline.transform(prompt,context)，再加入自己的策略。context只含观测、轮次和历史；禁止读ground truth。保持Layer输出原坐标、官方parser/validator/hash一致。只在dev调参并做消融，冻结后再运行test。

正式配置不可改：3×3、高度3、占用格数1/2/3，每层5个test观测，seed17/42/2026，temperature0.7、top_p0.9、top_k40、max_tokens512、context8192、repeat_penalty1，每题3/9/27次，总585次。用 python src/hypospace_runner.py --method 我的模块:transform --out 本机SSD/runs/我的方法；dev加--split dev。模型调用都算预算，修复/规划调用也不能隐藏；不得多生成筛选后只统计成功结果。额外预算实验必须让baseline用同样预算重新跑，单列结果。

用compare_runs.py比较相同配置和逐题预算，交代码、固定参数、精确命令、dev消融、总体与分层V/U/R、覆盖曲线、失败原因、调用数、输入输出tokens、总时间和局限。保留所有失败重复raw JSON在SSD供核查，提交小型指标和raw SHA256清单；不要提交权重、环境或大文件。论文已有历史去重及复杂度分层，创新必须说明新增点。每人通过独立分支提PR，另一人review，不直接推main。四人最后均参与10分钟视频讲解。
""",encoding='utf-8')
print(report,flush=True)
