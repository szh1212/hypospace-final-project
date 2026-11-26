"""Freeze exact local model digest before smoke and baseline runs."""
import sys,json
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p / ".git").exists());sys.path.insert(0,str(ROOT/'src'))
from ollama_client import OllamaClient
p=ROOT/'methods/szh-baseline-3d-task-b/experiments/protocol.json'; c=json.loads(p.read_text(encoding='utf-8'))
f=OllamaClient(c).fingerprint();c['model_digest']=f['digest']
p.write_text(json.dumps(c,indent=2)+'\n',encoding='utf-8')
(ROOT/'methods/szh-baseline-3d-task-b/experiments/model-lock.json').write_text(json.dumps(f,indent=2)+'\n',encoding='utf-8')
print(json.dumps(f,indent=2));print('Run hypospace_runner.py --prepare to update the config checksum.')
