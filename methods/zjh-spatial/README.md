# Spatial representation with occupied-column heights

Zhao Jianghan · Spatial Representation Transformation

The implementation, entry points, tests and published results are contained in this folder. The team's benchmark runner, baseline, datasets and scorer are shared dependencies. Local model weights and all raw responses are outside Git.

## Formal comparison

All formal rows use the same 15 top views, three seeds, fixed Qwen2.5-3B-Instruct model and 585 calls. Values are macro averages over observation–seed pairs.

| Method | Validity ↑ | Uniqueness ↑ | Recovery ↑ |
| --- | ---: | ---: | ---: |
| Adapted Baseline | 78.52% | 21.65% | 17.45% |
| Column planning with model-rendered layers | 44.69% | 32.84% | 17.70% |

The first method failed the acceptance criterion. Recovery changed by +0.25 percentage points with a 95% paired bootstrap interval of [−5.51, +5.60] points. Validity fell by 33.83 points. The raw audit found 292 projection errors and four unsupported stacks, making the rendering step a concrete target for the next version. [First formal comparison](reports/layer-test/comparison.json) · [First formal audit and examples](reports/layer-test/audit.json)

## First iteration

A valid stack is uniquely represented by the heights of the occupied cells, listed in row-major order. We labeled those cells, asked Qwen to choose one height per cell, and asked it to render layer `k` by marking the cells with heights at least `k`. An ablation showed prior valid stacks as compact ordered tuples. It retained prior grids when a tuple would lose information. The scorer received the model's ordinary `Layer` text directly.

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

Column planning with grid history had the highest development Recovery, up 6.79 percentage points from Adapted, with a 27.78-point loss in Validity. Compressing history saved tokens relative to column planning with grid history and lowered Recovery by 3.70 points. We froze `spatial_columns:grid_history` for test, using the implementation at `c1894a7`. These development results cover six observations with one seed and three calls each. [First development metrics](reports/layer-dev-comparison.json)

## Second iteration

The reversible height codec asks Qwen to supply one height per occupied cell and decodes the result into `Layer` grids in the original coordinates. In the text-only smoke test both variants generated three heights for each of the three one-cell calls. Each decoded 6 of 9 development responses. We added a JSON schema requiring exactly the right number of integer heights from 1 to 3. Both variants then decoded all 9 responses on the same smoke group. The schema defines the representation and leaves the height choices to Qwen. Unknown responses are forwarded unchanged. Each raw file preserves both the original model response and the scored text. [Smoke comparison](reports/codec-smoke-comparison.json)

The development comparison uses the full frozen development split with the Adapted prompt, the new fixed row-major order, and the new order that cycles the same occupied cells by one position per call. Both new variants present the same previously found stacks in the coordinate order of the current query. They leave the height values and coordinate-to-structure mapping intact. Cyclic order uses the query index alone and spends no extra calls.

Select the spatial variant on matched development instances. Prefer a variant that meets or exceeds Adapted Validity, then maximize macro Recovery and break ties on Validity. Keep fixed row-major order on an exact tie. A formal improvement requires higher macro Recovery with at least the Adapted point estimate for Validity. Report paired Recovery changes by seed and a 95% bootstrap interval resampling observations within each difficulty, with all seeds kept together for each sampled observation. This plan uses the development failure pattern and was recorded before reading the first formal results.

## Reproduction

Follow the [shared local setup](../../docs/local-setup.md) with the frozen model and upstream revision. The method uses CPU inference with the existing Qwen weights. Run from the repository root with the Python 3.12 environment active. The [protocol](../../experiments/protocol.json), [split](../../experiments/manifest.json), [model lock](../../experiments/model-lock.json) and Adapted prompt at starting revision `b8036b4` match the frozen Adapted Baseline revision `ddd0807`.

```powershell
$runs = Join-Path $env:USERPROFILE 'HypoSpaceLocal/runs/spatial-columns'
$method = 'methods/zjh-spatial'
$entry = "$method/experiments/run.py"
$reports = "$method/reports"
python -m unittest discover -s "$method/tests" -v
$hooks = @('adapted_baseline:transform', 'spatial_columns:grid_history', 'spatial_columns:transform')
foreach ($hook in $hooks) {
    $name = $hook.Replace(':', '-')
    foreach ($index in 0, 1) {
        python $entry --smoke --smoke-index $index --method $hook --out "$runs/dev/$name-$index"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
```

Commands for the initial 585-call test and the full development comparison of the schema-constrained variants.

```powershell
$test = Join-Path $runs 'test'
$report = "$reports/layer-test"
python $entry --method spatial_columns:grid_history --out $test
python src/export_run.py $test --out $report
python src/plot_results.py "$test/summary.json" --out $report
python "$method/experiments/compare.py" docs/figures/baseline/metrics.json "$report/metrics.json" --out "$report/comparison.json"
python "$method/experiments/audit.py" $test $report

$dev = "$runs/codec-dev"
python $entry --split dev --method adapted_baseline:transform --out "$dev/adapted"
python $entry --split dev --method spatial_codec:row_major --out "$dev/row-major"
python $entry --split dev --method spatial_codec:cyclic --out "$dev/cyclic"
python "$method/experiments/compare.py" "$dev/adapted/summary.json" "$dev/row-major/summary.json" "$dev/cyclic/summary.json" --select --out "$reports/codec-dev-comparison.json"
```
