"""Post-hoc diagnostics on unmodified outputs; never imported by generation."""
import collections,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'methods/common/szh-baseline-common'))
import run
out={}
for domain in ['causal','genetic']:
    mod=run.official(ROOT.parent/'upstream-hypospace',domain)
    levels=['causal'] if domain=='causal' else ['basic','extended','full']
    counts=collections.Counter();by_level={}
    for level in levels:
        ds=ROOT/'data/baseline-all-domains'/('causal.json' if domain=='causal' else f'boolean-{level}.json')
        bench=mod.CausalBenchmarkEnhanced(str(ds)) if domain=='causal' else mod.BooleanBenchmarkRefined(str(ds))
        cases={r['observation_set_id']:r for r in bench.all_observation_sets}
        cat=collections.Counter()
        for folder in sorted((ROOT/f'runs/all-domains/{domain}/test/raw/{level}').glob('*/*')):
            seen=set();case=cases[folder.name]
            for p in sorted(folder.glob('*.json')):
                record=run.read(p);h=bench.parse_llm_response(record['response']);cat['calls']+=1
                if h is None:cat['parser_rejection']+=1;continue
                if domain=='genetic' and not bench._in_space(h):cat['parsed_outside_space']+=1;continue
                s=run.score(bench,case,[record])
                if s['n_valid']==0:cat['observation_mismatch']+=1;continue
                key=h.get_hash() if domain=='causal' else str(bench.get_expression_mechanistic_key(h))
                cat['valid_duplicate' if key in seen else 'new_valid']+=1;seen.add(key)
        by_level[level]=dict(cat);counts.update(cat)
    report=run.read(ROOT/f'methods/task-{"a" if domain=="causal" else "c"}/szh-baseline-{domain}/reports/test.json')
    assert counts['calls']==report['completed_calls']
    assert counts['valid_duplicate']+counts['new_valid']==sum(r['n_valid'] for r in report['results'])
    out[domain]={'counts':dict(counts),'by_level':by_level}
(ROOT/'docs/baseline-all-domains/failure-diagnostics.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
