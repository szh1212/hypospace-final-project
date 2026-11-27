#!/bin/bash
# Sequential pipeline so a single local Ollama server is never contended.
# Code/protocol frozen: do not edit 3d/src or protocol-3d.json while this runs.
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH=src
run() { echo "===== $1 ====="; shift; python3 -u "$@"; }

run gen1-verbal src/hypospace_runner_3d.py --gen verbal --mode llm --split dev-smoke --out runs/verbal-dev-smoke
run gen2-free  src/hypospace_runner_3d.py --gen free   --mode llm --split dev-smoke --out runs/free-dev-smoke
run gen3-k2    src/hypospace_runner_3d.py --gen k2     --mode llm --split dev-smoke --out runs/k2-dev-smoke
run gen4-dev   src/hypospace_runner_3d.py --gen joint  --mode llm --split dev   --out runs/joint-dev
run gen4-test  src/hypospace_runner_3d.py --gen joint  --mode llm --split test  --out runs/joint-test
run official-test src/hypospace_runner_3d.py --gen official --mode llm --split test --out runs/official-test
echo "PIPELINE DONE"
