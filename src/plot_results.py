"""Compatibility entry; implementation lives in the method directory."""
from pathlib import Path
_target=Path(__file__).resolve().parents[1]/'methods/szh-baseline-3d-task-b/src/plot_results.py'
__file__=str(_target)
exec(compile(_target.read_bytes(),str(_target),"exec"),globals())
