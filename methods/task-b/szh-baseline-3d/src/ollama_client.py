"""Compatibility entry for the canonical shared utility."""
from pathlib import Path
_target=next(p for p in Path(__file__).resolve().parents if (p/".git").exists())/'methods/common/szh-baseline-common/compat/ollama_client.py'
__file__=str(_target)
exec(compile(_target.read_bytes(),str(_target),"exec"),globals())
