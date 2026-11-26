"""Compatibility import for the single shared Ollama transport."""
from pathlib import Path
_target=Path(__file__).resolve().parents[1]/'compat/ollama_client.py'
__file__=str(_target)
exec(compile(_target.read_bytes(),str(_target),'exec'),globals())
