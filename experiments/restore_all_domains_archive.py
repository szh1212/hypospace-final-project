"""Restore published raw records without inference or overwriting different files."""
import argparse,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--domain',choices=['causal','genetic'],required=True);a=p.parse_args()
folder=ROOT/f'methods/szh-baseline-{a.domain}/reports';out=(ROOT/f'runs/all-domains/{a.domain}/test').resolve();out.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
hashes={x['file'].replace('\\','/'):x['sha256'] for x in read(folder/'test-manifest.json')};visited=set()
with gzip.open(folder/'raw.jsonl.gz','rt',encoding='utf-8') as z:
 for line in z:
  entry=json.loads(line);name=entry['path'].replace('\\','/');raw=entry['utf8'].encode('utf-8');target=(out/name).resolve()
  if not target.is_relative_to(out) or name not in hashes or name in visited:raise ValueError('Unexpected archive path')
  if hashlib.sha256(raw).hexdigest()!=hashes[name]:raise ValueError('Archive hash mismatch')
  if target.exists():
   if target.read_bytes()!=raw:raise ValueError('Existing raw record differs')
  else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
  visited.add(name)
assert visited==set(hashes)
identity=(folder/'identity.json').read_bytes();dest=out/'identity.json'
if dest.exists():assert read(dest)==read(folder/'identity.json')
else:dest.write_bytes(identity)
print(f'Verified/restored {len(visited)} exact raw records; no inference')
