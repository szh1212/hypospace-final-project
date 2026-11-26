"""Run archived figure/report utilities with path-only ROOT rebinding."""
import ast,sys
from pathlib import Path
from integration_paths import RelocatedRoot,ROOT
name=sys.argv[1]
if name not in ['plot','report']:raise SystemExit('Choose plot or report')
p=ROOT/f'methods/szh-baseline-common/{name}.py';tree=ast.parse(p.read_bytes(),filename=str(p))
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ROOT' for t in node.targets):node.value=ast.Call(func=ast.Name(id='RelocatedRoot',ctx=ast.Load()),args=[],keywords=[])
ast.fix_missing_locations(tree);sys.argv=[str(p),*sys.argv[2:]]
exec(compile(tree,str(p),'exec'),{'__name__':'__main__','__file__':str(p),'RelocatedRoot':RelocatedRoot})
