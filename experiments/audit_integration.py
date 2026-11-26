"""Read-only integration audit: both 585-call baselines, no model inference."""
import json,gzip,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'experiments'),str(ROOT/'src')]
from verify_archive import VerifiedReplay
from hypospace_runner import upstream
bench=upstream()[0].Benchmark3D(str(ROOT/'data/3d.json'));obs={r['observation_id']:r for r in bench.all_observation_sets};results={}
for name in ['original','adapted']:
 folder=ROOT/f'methods/szh-baseline-3d-task-b/{name}/reports';m=json.loads((folder/'metrics.json').read_text());hashes={r['file']:r['sha256'] for r in json.loads((folder/'raw-manifest.json').read_text())};records={}
 with gzip.open(folder/'raw.jsonl.gz','rt',encoding='utf-8') as z:
  for line in z:
   e=json.loads(line);assert hashlib.sha256(e['utf8'].encode()).hexdigest()==hashes[e['path']];records[e['path']]=json.loads(e['utf8'])
 assert len(records)==585
 for r in m['results']:
  oid=r['observation_set_id'];seed=r['seed'];raw=[records[f'raw/{seed}/{oid}/{q:04d}.json'] for q in range(r['n_queries'])]
  replay=VerifiedReplay(raw,obs[oid]['observation'],seed+int(hashlib.sha256(oid.encode()).hexdigest()[:8],16),name=='adapted',m['identity']['config'])
  s=bench.evaluate_single_observation_set(replay,obs[oid],n_queries=len(raw),verbose=False,max_retries=1)
  for k in ['n_valid','n_unique','n_recovered_gts','valid_rate','novelty_rate','recovery_rate','token_usage']:assert s[k]==r[k],(name,oid,k)
 results[name]={'calls_replayed':585,'requests_hashes_scores_match':True}
Path('docs/integration-audit.json').write_text(json.dumps(results,indent=2));print(results)
