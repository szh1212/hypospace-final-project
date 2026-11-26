"""Compatibility entry; implementation lives in the method directory."""
from pathlib import Path
_target=Path(__file__).resolve().parents[1]/'methods/jcj-coverage-guided-task-b/tests/test_coverage_guided.py'
_legacy_file=__file__
__file__=str(_target)
exec(compile(_target.read_bytes(),str(_target),"exec"),globals())

__file__=_legacy_file
