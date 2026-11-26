"""Replay the frozen runner, comparing summaries in their JSON serialization domain.
CausalGraph.to_dict retains tuples in memory; stored JSON necessarily uses lists.
No metrics, requests, sources, configurations or raw responses are modified.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'methods/szh-baseline-common'))
import run
class JsonSummary(dict):
    def __eq__(self,other):
        return json.dumps(self,sort_keys=True,separators=(',',':'))==json.dumps(other,sort_keys=True,separators=(',',':'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--domain',choices=['causal','genetic'],required=True);a=p.parse_args()
    target=(ROOT/f'methods/szh-baseline-{a.domain}/reports/test.json').resolve()
    original=run.read
    def read(path):
        value=original(path)
        return JsonSummary(value) if Path(path).resolve()==target else value
    run.read=read
    sys.argv=[str(ROOT/'methods/szh-baseline-common/run.py'),'--domain',a.domain,'--stage','audit']
    run.main()
if __name__=='__main__':main()
