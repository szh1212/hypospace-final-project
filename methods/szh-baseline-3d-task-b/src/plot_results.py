"""Plot actual saved measurements; offline results are explicitly labeled."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
p=argparse.ArgumentParser(); p.add_argument('summary'); p.add_argument('--out',required=True); a=p.parse_args()
d=json.loads(Path(a.summary).read_text(encoding='utf-8')); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
label='OFFLINE uniform-height control (NOT LLM)' if d['identity']['mode']=='offline' else d['identity']['config']['model']+' / '+d['identity']['method']
fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,m,title in zip(axs,['valid_rate','novelty_rate','recovery_rate'],['Validity V','Uniqueness U','Recovery R']):
    for b in [1,2,3]:
        rows=[r for r in d['curves'] if r['blocks']==b]; ks=sorted(set(r['k'] for r in rows))
        means=[np.mean([r[m] for r in rows if r['k']==k]) for k in ks]
        ax.plot(ks,means,label=f'{b} occupied cells; |H|={3**b}')
    ax.set(title=title,xlabel='Proposals per observation (calls)',ylabel='Macro mean (fraction)',ylim=(-.03,1.05)); ax.grid(alpha=.2)
axs[2].legend(fontsize=8); fig.suptitle(label+f"\n{len(set(r['observation_set_id'] for r in d['results']))} observations x {len(set(r['seed'] for r in d['results']))} repeats; pinned HypoSpace evaluator",fontsize=12)
fig.savefig(out/'curves.png',dpi=180); fig.savefig(out/'curves.pdf'); plt.close(fig)
# Display actual recovered hypotheses from first largest-stratum task.
r=next(r for r in d['results'] if r['blocks']==3)
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from hypospace_runner import upstream
mod,_=upstream(); bench=object.__new__(mod.Benchmark3D)
fig=plt.figure(figsize=(10,9)); fig.suptitle(label+'\nFirst four parsed distinct proposals (not selected by validity)')
for i,text in enumerate(r['unique_structures'][:4]):
    s=bench.parse_llm_response(text); vox=np.stack(s.layers,axis=2).astype(bool)
    ax=fig.add_subplot(2,2,i+1,projection='3d'); ax.voxels(vox,facecolors='#4386b0',edgecolor='white',linewidth=.4)
    ax.text2D(.83,.82,'height',transform=ax.transAxes,fontsize=9); ax.set_zticks([0,1,2,3]); ax.tick_params(labelsize=8)
    ax.set(xlabel='row',ylabel='column',zlabel='',zlim=(0,3),title=f'Proposal {i+1}')
fig.subplots_adjust(left=.04,right=.90,bottom=.05,top=.87,wspace=.30,hspace=.25); fig.savefig(out/'structures.png',dpi=180,bbox_inches='tight'); plt.close(fig)
print(out)
