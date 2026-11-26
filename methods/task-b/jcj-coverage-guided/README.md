# JCJ coverage-guided generation — Task B

Algorithm: src/coverage_guided.py. Frozen inference configuration and official evaluator are shared with ../szh-baseline-3d-task-b/. Formal results and figures are preserved in reports/; the submitted scientific report and paired comparison are in docs/.

The original raw responses are NOT included in this repository. reports/raw-manifest.json retains the submitted 585-file SHA256 inventory. JCJ results are adopted from its submitted formal report; independent per-call historical replay was NOT performed. No replacement records or new inference were generated during integration.

From repository root: `python src/hypospace_runner.py --method coverage_guided:transform --out runs/cg-new`; audit an available original run with `python experiments/validate_coverage.py <run-directory>`. Tests: `python -m unittest discover -s methods/task-b/jcj-coverage-guided/tests -v`.
