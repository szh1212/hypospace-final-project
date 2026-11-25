"""Verify every raw request and replay every scored response for a published run."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


METHOD = Path(__file__).resolve().parents[1]
PROJECT = METHOD.parents[1]
sys.path[:0] = [str(METHOD / 'src'), str(PROJECT / 'src')]

from experiment_api import evaluate_outputs, load_dataset
from hypospace_runner import digest, upstream
from spatial_codec import decode_cyclic, decode_row_major


DECODERS = {'spatial_codec:row_major': decode_row_major, 'spatial_codec:cyclic': decode_cyclic}
SCORES = ('n_valid', 'n_unique', 'n_recovered_gts', 'valid_rate', 'novelty_rate', 'recovery_rate')


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit(raw_root, export):
    metrics = _read(export / 'metrics.json')
    manifest = _read(export / 'raw-manifest.json')
    hashes = {item['file']: item['sha256'] for item in manifest}
    files = {path.relative_to(raw_root).as_posix() for path in (raw_root / 'raw').rglob('*.json')}
    if len(manifest) != len(hashes) or hashes.keys() != files or len(files) != metrics['completed_calls']:
        raise ValueError('Manifest, raw files and total calls differ')

    observations = {item['observation_id']: item['observation']
                    for item in load_dataset(metrics['identity']['split'])}
    decoder = DECODERS.get(metrics['identity']['method'])
    official, _ = upstream()
    parser = object.__new__(official.Benchmark3D)
    outcomes, encodings, examples, verified = Counter(), Counter(), {}, set()
    for row in metrics['results']:
        oid, seed = row['observation_set_id'], row['seed']
        observation, scored, prior_valid = observations[oid], [], set()
        for index in range(row['n_queries']):
            name = f'raw/{seed}/{oid}/{index:04d}.json'
            raw = (raw_root / name).read_bytes()
            if name in verified or hashlib.sha256(raw).hexdigest() != hashes[name]:
                raise ValueError(f'Raw record mismatch: {name}')
            verified.add(name)
            record = json.loads(raw)
            if digest(record['request']) != record['request_sha256']:
                raise ValueError(f'Request digest mismatch: {name}')

            response = record['response']
            if decoder:
                model_text = record['raw_response']
                context = {'observation': observation, 'query_index': index}
                if decoder(model_text, context) != response or record['code_decoded'] != (model_text != response):
                    raise ValueError(f'Decoder mismatch: {name}')
                encodings['decoded' if record['code_decoded'] else 'forwarded unchanged'] += 1
            scored.append(response)

            projection = None
            structure = parser.parse_llm_response(response)
            if structure is None:
                outcome = 'parse failure'
            else:
                structure = structure.normalize()
                projection = ''.join(map(str, structure.get_top_view().ravel()))
                if not parser.validate_structure_matches_observations(structure, observation):
                    outcome = 'projection mismatch' if projection != observation else 'unsupported'
                else:
                    key = structure.get_hash()
                    outcome = 'valid duplicate' if key in prior_valid else 'new valid'
                    prior_valid.add(key)
            outcomes[outcome] += 1
            examples.setdefault(outcome, {
                'file': name, 'observed_projection': observation, 'returned_projection': projection,
                'model_response_excerpt': record.get('raw_response', response)[:400],
                'scored_response_excerpt': response[:400],
            })

        scores = evaluate_outputs(oid, scored)
        if any(scores[key] != row[key] for key in SCORES):
            raise ValueError(f'Official replay mismatch: {oid}, seed {seed}')
    if verified != files:
        raise ValueError('Some raw records were not replayed')
    return {'verified_calls': len(verified), 'outcomes': outcomes, 'codec': encodings, 'examples': examples}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('raw_root', type=Path)
    cli.add_argument('export', type=Path)
    args = cli.parse_args()
    report = audit(args.raw_root, args.export)
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    (args.export / 'audit.json').write_text(text, encoding='utf-8')
    print(text)
