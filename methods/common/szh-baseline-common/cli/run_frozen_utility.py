"""Run archived figure/report utilities with path-only ROOT rebinding."""
import ast,sys
from pathlib import Path
_REPO=next(p for p in Path(__file__).resolve().parents if (p/".git").exists())
sys.path[:0]=[str(_REPO/"src"),str(_REPO/"experiments")]

from integration_paths import RelocatedRoot,ROOT
name=sys.argv[1]
if name not in ['plot','report','prepare_data']:raise SystemExit('Choose plot, report or prepare_data')
p=ROOT/f'methods/common/szh-baseline-common/{name}.py';tree=ast.parse(p.read_bytes(),filename=str(p))
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ['ROOT','root'] for t in node.targets):node.value=ast.Call(func=ast.Name(id='RelocatedRoot',ctx=ast.Load()),args=[],keywords=[])
ast.fix_missing_locations(tree);sys.argv=[str(p),*sys.argv[2:]]
exec(compile(tree,str(p),'exec'),{'__name__':'__main__','__file__':str(p),'RelocatedRoot':RelocatedRoot})
