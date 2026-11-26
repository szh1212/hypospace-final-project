"""Sustained foreground execution; no synthetic outputs or model fallback."""
import json,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def invoke(domain,stage):
    cmd=[sys.executable,str(ROOT/'methods/szh-baseline-common/run.py'),'--stage',stage]
    if domain:cmd+=['--domain',domain]
    subprocess.run(cmd,cwd=ROOT,check=True)
start=time.monotonic()
while True:
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as r: tags=json.load(r)
    if any(m['name']=='qwen2.5:3b-instruct-q4_K_M' for m in tags['models']):break
    if time.monotonic()-start>3600:raise RuntimeError('Model download not ready after one hour; inspect local download')
    print(json.dumps({'stage':'waiting_for_exact_model','A_completed':0,'A_planned':2019,'C_completed':0,'C_planned':270}),flush=True)
    time.sleep(30)
for d in ['causal','genetic']:invoke(d,'smoke')
invoke(None,'freeze')
for d in ['genetic','causal']:
    invoke(d,'test');invoke(d,'audit')
subprocess.run([sys.executable,str(ROOT/'methods/szh-baseline-common/plot.py')],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'methods/szh-baseline-common/report.py')],cwd=ROOT,check=True)
print('INFERENCE_AND_REPLAY_FINISHED',flush=True)
