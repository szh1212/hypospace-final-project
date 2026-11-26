"""Compatibility entry for the shared 3D utility."""
from pathlib import Path
import sys
_repo=next(p for p in Path(__file__).resolve().parents if (p/".git").exists())
sys.path.insert(0,str(_repo/"src"))
_target=_repo/'methods/common/szh-baseline-common/three_d/plot_results.py'
__file__=str(_target)
exec(compile(_target.read_bytes(),str(_target),"exec"),globals())
