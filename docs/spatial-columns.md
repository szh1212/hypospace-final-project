# Spatial representation with occupied-column heights

Zhao Jianghan · Spatial Representation Transformation

A valid stack is uniquely represented by the heights of the occupied cells, listed in row-major order. The observation determines the occupied cells. For each model call, label those cells by their original row and column, ask the model to choose one height per cell, and ask it to render layer `k` by marking each listed cell whose height is at least `k`. The model returns the ordinary `Structure` and `Layer` grids in the original coordinates. The runner sends its raw response directly to official scoring.

The full method also represents previous legal stacks as height tuples in the same order. This makes two stacks comparable from one short line each. The implementation reuses the Adapted prompt's unique parsed history, keeps entries in their original order, and leaves previous grids in layer form when a tuple would lose information. The generator sees only the observation and its own earlier responses. Each call still generates one proposal.

## Development comparison

Use both development smoke groups for a matched screen: three proposals per observation on the six development observations, with seed 17. This gives 18 proposals per arm. Record macro Recovery first, with Validity, Uniqueness and token use alongside it. The first difference estimates the effect of the column representation in the prompt. The second estimates the additional effect of encoding the history. Select between the two spatial variants on development macro Recovery, breaking ties on Validity, then preferring the simpler grid-history variant. Freeze the choice and code before running the 585-call test against the published Adapted Baseline. The shortened development runs can miss repetition that emerges with longer histories.

| Arm | Runner hook | Spatial representation |
| --- | --- | --- |
| Adapted | `adapted_baseline:transform` | Layer grids for both instructions and prior outputs |
| Column planning | `spatial_columns:grid_history` | Occupied-column planning with layer-grid history |
| Column planning and history | `spatial_columns:transform` | Occupied-column planning with compact history for representable stacks |

The hypothesis is that the column representation reduces accidental changes to the footprint and makes previously explored structures easier to compare. Rendering the tuple back into grids adds a step for a small model, which can introduce projection or support errors. The measurements will show how these effects trade off.

| Development arm | Calls | Validity | Uniqueness | Recovery | Input / output tokens | Request seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adapted | 18 | 100.00% | 38.89% | 17.90% | 5,068 / 930 | 116.18 |
| Column planning | 18 | 72.22% | 55.56% | 24.69% | 7,214 / 1,483 | 164.19 |
| Column planning and history | 18 | 66.67% | 55.56% | 20.99% | 6,875 / 1,265 | 133.06 |

Column planning with grid history had the highest development Recovery, up 6.79 percentage points from Adapted, with a 27.78-point loss in Validity. Compressing history saved tokens relative to column planning with grid history and lowered Recovery by 3.70 points. We froze `spatial_columns:grid_history` for test, using the implementation at `c1894a7`. These development results cover six observations with one seed and three calls each. [Development metrics](figures/spatial-columns/dev-comparison.json)

## Second iteration plan

The first development screen improved Recovery but lost Validity. Its prompts asked Qwen to plan heights and then reconstruct the full layer grids. The next iteration moves the coordinate inverse into a deterministic decoder. Qwen supplies one height per occupied cell. Each well-formed height code maps to exactly one stack in the original coordinates. The evaluator receives the decoded `Layer` grids. Unrecognized responses are forwarded unchanged and remain in the call budget. The audit retains the original response and the exact response scored.

The development comparison uses the full frozen development split with the Adapted prompt, the new fixed row-major order, and the new order that cycles the same occupied cells by one position per call. Both new variants present the same previously found stacks in the coordinate order of the current query. They leave the height values and coordinate-to-structure mapping intact. Cyclic order uses the query index alone and spends no extra calls.

Select the spatial variant on matched development instances. Prefer a variant that meets or exceeds Adapted Validity, then maximize macro Recovery and break ties on Validity. Keep fixed row-major order on an exact tie. A formal improvement requires higher macro Recovery with at least the Adapted point estimate for Validity. Report paired Recovery changes by seed and a 95% bootstrap interval resampling observations within each difficulty, with all seeds kept together for each sampled observation. This plan uses the development failure pattern and was recorded before reading the first formal results.

## Reproduction

Follow the [local setup](local-setup.md) with the frozen model and upstream benchmark. The script uses local CPU inference with the existing Qwen weights. Keep the virtual environment, model and raw responses on the local SSD, outside this repository. Run from the repository root with the Python 3.12 environment active.

```powershell
$runs = Join-Path $env:USERPROFILE 'HypoSpaceLocal/runs/spatial-columns'
python -m unittest discover -s tests -v
$hooks = @('adapted_baseline:transform', 'spatial_columns:grid_history', 'spatial_columns:transform')
foreach ($hook in $hooks) {
    $name = $hook.Replace(':', '-')
    foreach ($index in 0, 1) {
        python src/hypospace_runner.py --smoke --smoke-index $index --method $hook --out "$runs/dev/$name-$index"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
```

The [experiment protocol](../experiments/protocol.json), [split manifest](../experiments/manifest.json), [model lock](../experiments/model-lock.json), and Adapted prompt on the starting revision `b8036b4` match the frozen Adapted Baseline revision `ddd0807`.

Run the selected method with all 15 frozen test observations, their three seeds and the original 585-call budget. Keep raw responses on the SSD and export only the compact metrics, checksum list and figures to the repository.

```powershell
$test = Join-Path $runs 'test'
$report = 'docs/figures/spatial-columns/test'
python src/hypospace_runner.py --method spatial_columns:grid_history --out $test
python src/export_run.py $test --out $report
python src/plot_results.py "$test/summary.json" --out $report
python src/compare_runs.py docs/figures/baseline/metrics.json "$report/metrics.json" --out "$report/comparison.json"
```
