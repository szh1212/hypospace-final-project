"""Pack frozen raw model responses, or restore them to a new directory for offline replay."""
import argparse
import gzip
import json
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "runs/parent-strata-raw.tar.gz"
SPLITS = ("dev", "test")
MEMBER = re.compile(
    r"(dev|test)/(identity\.json|summary\.json|"
    r"raw/n[12]_[0-9]{3}/[0-9]+/[a-z_]+/[0-9]{3}\.json)"
)


def expected_files(base, split):
    summary = json.loads((base / "summary.json").read_text())
    identity = json.loads((base / "identity.json").read_text())
    if summary["split"] != split or summary["identity"] != identity or identity["split"] != split:
        raise ValueError(f"Inconsistent summary or identity in {base}")
    protocol = summary["protocol"]
    cells = {(case, seed, method) for case in protocol[split]
             for seed in protocol[split + "_seeds"] for method in protocol["methods"]}
    recorded = [(row["case_id"], row["seed"], row["method"]) for row in summary["rows"]]
    if len(recorded) != len(cells) or set(recorded) != cells:
        raise ValueError(f"Incomplete cell summary in {base}")
    paths = ["identity.json", "summary.json"]
    for case, seed, method in sorted(cells):
        for step in range(protocol["budget"]):
            rel = f"raw/{case}/{seed}/{method}/{step:03}.json"
            if not MEMBER.fullmatch(f"{split}/{rel}"):
                raise ValueError(f"Unexpected record name {rel}")
            paths.append(rel)
    return paths


def pack(runs, archive):
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=archive.parent) as tmp:
        with gzip.GzipFile(filename="", mode="wb", fileobj=tmp, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w|") as tar:
                for split in SPLITS:
                    base = runs / f"parent-{split}"
                    for rel in expected_files(base, split):
                        path = base / rel
                        info = tarfile.TarInfo(f"{split}/{rel}")
                        info.size = path.stat().st_size
                        with path.open("rb") as src:
                            tar.addfile(info, src)
        tmp.flush()
        os.link(tmp.name, archive)  # Publish only after completion; never replace another archive.


def restore(archive, destination):
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Choose a new restore directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        root = Path(staging) / "restored"
        restored = set()
        with tarfile.open(archive, "r:gz") as tar:
            for entry in tar:
                if not entry.isfile() or not MEMBER.fullmatch(entry.name) or entry.name in restored:
                    raise ValueError(f"Unexpected archive member {entry.name!r}")
                target = root / entry.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as output:
                    shutil.copyfileobj(tar.extractfile(entry), output)
                restored.add(entry.name)
        expected = {f"{split}/{rel}" for split in SPLITS for rel in expected_files(root / split, split)}
        if restored != expected:
            raise ValueError("Archive members differ from the frozen experiment protocol")
        root.rename(destination)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    create = commands.add_parser("pack", help="Read runs/parent-dev and runs/parent-test.")
    create.add_argument("--runs", type=Path, default=ROOT / "runs")
    create.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    extract = commands.add_parser("restore", help="Use --out <destination>/<split> in the replay runner.")
    extract.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    extract.add_argument("--destination", type=Path, required=True)
    args = cli.parse_args()
    if args.command == "pack":
        pack(args.runs, args.archive)
    else:
        restore(args.archive, args.destination)


if __name__ == "__main__":
    main()
