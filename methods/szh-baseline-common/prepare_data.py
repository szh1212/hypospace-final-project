"""Generate ignored official reference data deterministically; never used for generation."""
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
up=root.parent/'upstream-hypospace'
env=dict(os.environ,PYTHONHASHSEED='0',PYTHONIOENCODING='utf-8')
for level in ['basic','extended','full']:
    subprocess.run([sys.executable,str(up/'boolean/boolean_dataset.py'),'--operators',level,'--max-depth','2','--seed','33550336','--output',str(root/f'data/baseline-all-domains/boolean-{level}.json')],env=env,check=True)
subprocess.run([sys.executable,str(up/'causal/generate_causal_dataset.py'),'--nodes','4','--max-edges','4','--n-observations','2','--seed','33550336','--output',str(root/'data/baseline-all-domains/causal.json')],env=env,check=True)
