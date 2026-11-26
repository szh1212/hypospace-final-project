"""Compatibility entry; implementation lives in the method directory."""
from pathlib import Path
_target=Path(__file__).resolve().parents[1]/'methods/task-b/jcj-coverage-guided/src/coverage_guided.py'
__file__=str(_target)
exec(compile(_target.read_bytes(),str(_target),"exec"),globals())
