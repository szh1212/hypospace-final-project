# 在本机SSD复现

Windows需Python 3.12、Git和Ollama 0.40.18。Ollama官方版本：https://github.com/ollama/ollama/releases/tag/v0.40.18 。模型tag：qwen2.5:3b-instruct-q4_K_M（必须核对仓库model-lock，不使用cloud tag）。

以下命令中 LocalRoot 请替换为本机SSD上的目录；仓库可以另放，但环境和模型不要放U盘。不要在Git目录内存密钥（本项目完全不需要密钥）。

```powershell
$LocalRoot = "$env:USERPROFILE\HypoSpaceLocal"
New-Item -ItemType Directory -Force $LocalRoot
python -m venv "$LocalRoot\.venv"
git clone -b szh/baseline-3d https://github.com/szh1212/hypospace-final-project.git
cd hypospace-final-project
& "$LocalRoot\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

先安装固定版本Ollama到本机SSD。本仓库提供可选CPU专用安装器：先用SSD虚拟环境安装 remotezip==0.12.6，再运行 `python methods/szh-baseline-3d-task-b/experiments/install_ollama_cpu.py <SSD目录>/ollama`；它只从官方固定版本便携包提取CPU组件，不下载无用的CUDA库。已存在的Ollama服务必须使用正确的SSD模型目录；start_ollama.ps1不会终止已有服务，也不会搬迁别人的模型。若用官方便携包，可解压到LocalRoot/ollama；普通安装则使用PATH上的ollama。

```powershell
powershell -ExecutionPolicy Bypass -File methods/szh-baseline-3d-task-b/experiments/start_ollama.ps1 -LocalRoot $LocalRoot
# 便携安装使用绝对路径；普通安装可以直接用 ollama
& "$LocalRoot\ollama\ollama.exe" pull qwen2.5:3b-instruct-q4_K_M
& "$LocalRoot\.venv\Scripts\python.exe" methods/szh-baseline-3d-task-b/experiments/bootstrap.py
& "$LocalRoot\.venv\Scripts\python.exe" methods/szh-baseline-3d-task-b/src/hypospace_runner.py --prepare
& "$LocalRoot\.venv\Scripts\python.exe" -m unittest discover -s tests -v
& "$LocalRoot\.venv\Scripts\python.exe" methods/szh-baseline-3d-task-b/src/hypospace_runner.py --smoke --out "$LocalRoot\runs\smoke"
```

队友不要运行freeze_model.py来覆盖已提交的锁；遇到digest/version mismatch应安装指定版本，不能把不一致的模型当成同一实验。

正式基线/方法的命令：

```powershell
& "$LocalRoot\.venv\Scripts\python.exe" methods/szh-baseline-3d-task-b/src/hypospace_runner.py --method adapted_baseline:transform --out "$LocalRoot\runs\baseline"
& "$LocalRoot\.venv\Scripts\python.exe" methods/szh-baseline-3d-task-b/src/hypospace_runner.py --method my_method:transform --out "$LocalRoot\runs\my-method"
& "$LocalRoot\.venv\Scripts\python.exe" methods/szh-baseline-3d-task-b/src/plot_results.py "$LocalRoot\runs\my-method\summary.json" --out docs/figures/my-method
& "$LocalRoot\.venv\Scripts\python.exe" methods/szh-baseline-3d-task-b/src/compare_runs.py methods/szh-baseline-3d-task-b/adapted/reports/metrics.json "$LocalRoot\runs\my-method\summary.json" --out docs/my-method-comparison.json
```

原始输出会保存在各自SSD的runs下。恢复中断运行用相同命令；不同设置用新目录。dev调参加 --split dev，test前冻结代码和超参数。Linux/macOS可用同样Python命令和本机Ollama，环境路径改为.venv/bin/python，并保持版本和配置一致；跨后端逐字复现没有保证。
