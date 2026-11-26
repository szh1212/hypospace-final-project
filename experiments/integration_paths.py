"""Path-only compatibility for frozen all-domain sources and archived identities."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MAPPING=json.loads((ROOT/'methods/szh-baseline-common/path_compat.txt').read_text(encoding='utf-8'))
class RelocatedRoot:
 parent=ROOT.parent
 def __truediv__(self,value):
  text=str(value).replace('\\','/')
  for old,new in sorted(MAPPING.items(),key=lambda kv:-len(kv[0])):
   if text==old or text.startswith(old+'/'):return ROOT/(new+text[len(old):])
  return ROOT/text

def configure(module):module.ROOT=RelocatedRoot()
