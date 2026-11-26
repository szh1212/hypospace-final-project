"""Read-only replay of the already published 3D adapted archive; no inference."""
import gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'experiments'),str(ROOT/'src')]
from verify_archive import VerifiedReplay
from hypospace_runner import upstream
folder=ROOT/'docs/figures/baseline'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
metrics=read(folder/'metrics.json');manifest={r['file']:r['sha256'] for r in read(folder/'raw-manifest.json')}
raw={}
with gzip.open(folder/'raw.jsonl.gz','rt',encoding='utf-8') as stream:
    for line in stream:
        entry=json.loads(line);name=entry['path'];assert name not in raw
        assert hashlib.sha256(entry['utf8'].encode()).hexdigest()==manifest[name]
        raw[name]=json.loads(entry['utf8'])
assert set(raw)==set(manifest) and len(raw)==585
bench=upstream()[0].Benchmark3D(str(ROOT/'data/3d.json'))
obs={o['observation_id']:o for o in bench.all_observation_sets}
for row in metrics['results']:
    oid=row['observation_set_id'];seed=row['seed']
    records=[raw[f'raw/{seed}/{oid}/{q:04d}.json'] for q in range(row['n_queries'])]
    replay=VerifiedReplay(records,obs[oid]['observation'],seed+int(hashlib.sha256(oid.encode()).hexdigest()[:8],16),True,metrics['identity']['config'])
    scored=bench.evaluate_single_observation_set(replay,obs[oid],n_queries=len(records),verbose=False,max_retries=1)
    for k in ['n_valid','n_unique','n_recovered_gts','valid_rate','novelty_rate','recovery_rate','token_usage']:assert scored[k]==row[k],(oid,seed,k)
out=ROOT/'docs/baseline-all-domains/historical-3d-replay.json'
out.write_text(json.dumps({'status':'VERIFIED','raw_calls':585,'all_request_hashes_and_scores_match':True,'inference_calls':0},indent=2),encoding='utf-8')
print(out)
