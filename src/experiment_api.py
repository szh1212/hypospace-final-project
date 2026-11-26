"""Reusable data/evaluation interfaces. Ground truth stays on the evaluator side."""
import json
from hypospace_runner import ROOT, digest, upstream, Replay

def load_dataset(split='test'):
    data=json.loads((ROOT/'data/3d.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'experiments/manifest.json').read_text(encoding='utf-8'))
    if digest(data)!=manifest['dataset_sha256']: raise ValueError('Dataset checksum mismatch')
    ids=manifest['splits'][split]
    return [dict(observation_id=o['observation_id'],observation=o['observation']) for o in data['observation_sets'] if o['observation_id'] in ids]

def evaluate_outputs(observation_id, outputs):
    """Score ALL generated responses, including failures/duplicates, with official metrics."""
    if not outputs: raise ValueError('At least one proposal is required')
    official,_=upstream()
    b=official.Benchmark3D(str(ROOT/'data/3d.json'))
    obs=next(o for o in b.all_observation_sets if o['observation_id']==observation_id)
    return b.evaluate_single_observation_set(Replay([{'response':s} for s in outputs]),obs,n_queries=len(outputs),verbose=False,max_retries=1)
