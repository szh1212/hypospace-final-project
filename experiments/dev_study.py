import sys,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from hypospace_runner import upstream,Replay,save
m,_=upstream(); b=m.Benchmark3D(str(ROOT/'data/3d.json'))
checks=[]
for obs in b.all_observation_sets:
    for gt in obs['ground_truth_structures']:
        rows=[[[int(c) for c in layer[i:i+3]] for i in range(0,9,3)] for layer in gt['layers']]
        s=m.Structure3D(rows); parsed=b.parse_llm_response('Structure:\n'+s.to_string())
        assert parsed and parsed.get_hash()==s.get_hash()
        assert b.validate_structure_matches_observations(parsed,obs['observation'])
        checks.append(s.get_hash())
save(ROOT/'docs/evaluator-check.json',{'observations':len(b.all_observation_sets),'legal_structures_checked':len(checks),'all_passed':True,'checks':['legal structure -> text -> parser hash roundtrip','projection and support validity']})
local=Path.home()/'HypoSpaceLocal/runs'
for method in ['structured','coordinates','reasoning']:
    subprocess.run([sys.executable,str(ROOT/'src/hypospace_runner.py'),'--smoke','--method','dev_prompts:'+method,'--out',str(local/('dev-'+method))],cwd=ROOT,check=True)
print('DEV STUDY COMPLETE',flush=True)
