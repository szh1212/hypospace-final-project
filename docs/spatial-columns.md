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
