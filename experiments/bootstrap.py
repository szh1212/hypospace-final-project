"""Fetch the pinned benchmark without vendoring it into the team repository."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'.cache/hypospace'
PIN='c69e9318577b34b5b896996571aefd4ba6053f58'
if not path.exists():
    subprocess.run(['git','clone','https://github.com/CTT-Pavilion/_HypoSpace.git',str(path)],check=True)
subprocess.run(['git','-c',f'safe.directory={path.as_posix()}','-C',str(path),'checkout',PIN],check=True)
