"""Relabel raw request records to a new method name without touching the payload.

Used when a method variant shares prompts and sampling with an existing frozen
run, so its raw responses are reused verbatim: only the request-id method label
is rewritten; the payload hash is recomputed and left consistent with the
unchanged payload.
"""
import argparse
import json
from pathlib import Path
import sys

from run_causal import ROOT, digest

sys.path.insert(0, str(ROOT / "experiments"))


def relabel(folder, new_method):
    count = 0
    for path in sorted(Path(folder).rglob("*.json")):
        if path.name in ("identity.json", "summary.json"):
            continue
        record = json.loads(path.read_text())
        data = record["data"]
        record["data_sha256"] = digest(data)
        record["request_id"] = digest([data["prompt"], data["seed"], new_method, 0])
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    print(f"relabeled {relabel(args.folder, args.method)} records")
