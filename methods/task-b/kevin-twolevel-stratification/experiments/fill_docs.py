"""Fill docs/experiment-results-3d.md from the analysis JSON + run summaries."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pct(x, plus=False):
    s = f'{x * 100:.2f}%'
    return f'{x * 100:+.2f}pp' if plus else s


def fmt_paired(d):
    return (f"{d['mean'] * 100:+.2f}pp [{d['ci95'][0] * 100:+.2f}, "
            f"{d['ci95'][1] * 100:+.2f}]（{d['wins']}/{d['n_units']} 胜）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', default='runs/analysis-3d.json')
    args = ap.parse_args()
    a = json.loads((ROOT / args.analysis).read_text(encoding='utf-8'))
    m = a['macros']
    pr = a['prefix_recovery']
    paired = a['paired']
    per_case = a['per_case']

    dv, du, dr = [fmt_paired(paired['final_vs_baseline']['metrics'][x])
                  for x in ('valid_rate', 'novelty_rate', 'recovery_rate')]
    dv_off, du_off, dr_off = [fmt_paired(paired['final_vs_official']['metrics'][x])
                              for x in ('valid_rate', 'novelty_rate', 'recovery_rate')]
    dv_ol, du_ol, dr_ol = [fmt_paired(paired['final_vs_offline']['metrics'][x])
                           for x in ('valid_rate', 'novelty_rate', 'recovery_rate')]

    per_case_rows = []
    for row in per_case:
        b, f = row['baseline'], row['final']
        per_case_rows.append(
            f"| {row['case']} | {pct(b['valid_rate'])} / {pct(b['novelty_rate'])} / {pct(b['recovery_rate'])} "
            f"| {pct(f['valid_rate'])} / {pct(f['novelty_rate'])} / {pct(f['recovery_rate'])} |")

    def g(name):
        v = m[name]
        return v['valid_rate'], v['novelty_rate'], v['recovery_rate']

    v_o, u_o, r_o = g('official_test')
    v_ol, u_ol, r_ol = g('offline_test')
    v_s, u_s, r_s = g('baseline')
    v_g1, u_g1, r_g1 = g('gen1_dev_smoke')
    v_g2, u_g2, r_g2 = g('gen2_dev_smoke')
    v_g3, u_g3, r_g3 = g('gen3_dev_smoke')
    v_f, u_f, r_f = g('final_test')
    v_fd, u_fd, r_fd = g('final_dev')
    v_fs, u_fs, r_fs = g('final_dev_smoke')

    pf, pb = pr['final'], pr['baseline']

    def prget(name, k, default=0.0):
        d = pr.get(name)
        if not d:
            return default
        return d.get(str(k), d.get(k, default))

    # SZH prefix R columns (clamped per-case)
    r1s, r3s, r9s, r27s = pct(prget('baseline', 1)), pct(prget('baseline', 3)), pct(prget('baseline', 9)), pct(prget('baseline', 27))
    r1f, r3f, r9f, r27f = pct(prget('final', 1)), pct(prget('final', 3)), pct(prget('final', 9)), pct(prget('final', 27))
    r1o, r3o, r9o, r27o = pct(prget('official', 1)), pct(prget('official', 3)), pct(prget('official', 9)), pct(prget('official', 27))
    r1l, r3l, r9l, r27l = pct(prget('offline', 1)), pct(prget('offline', 3)), pct(prget('offline', 9)), pct(prget('offline', 27))

    tpl = (ROOT / 'docs' / 'experiment-results-3d.md').read_text(encoding='utf-8')

    def sub(template, **kw):
        out = template
        for k, val in kw.items():
            out = out.replace('{{' + k + '}}', str(val))
        return out

    out = sub(
        tpl,
        V_OFFICIAL=pct(v_o), U_OFFICIAL=pct(u_o),
        R1_OFFICIAL=r1o, R3_OFFICIAL=r3o, R9_OFFICIAL=r9o, R27_OFFICIAL=r27o,
        R1_OFFLINE=r1l, R3_OFFLINE=r3l, R9_OFFLINE=r9l, R27_OFFLINE=r27l,
        R1_SZH=r1s, R3_SZH=r3s, R9_SZH=r9s,
        V_G1=pct(v_g1), U_G1=pct(u_g1),
        V_G2=pct(v_g2), U_G2=pct(u_g2),
        V_G3=pct(v_g3), U_G3=pct(u_g3),
        V_FINAL=pct(v_f), U_FINAL=pct(u_f),
        R1_FINAL=r1f, R3_FINAL=r3f, R9_FINAL=r9f, R27_FINAL=r27f,
        DV_OFFICIAL=dv_off, DU_OFFICIAL=du_off, DR_OFFICIAL=dr_off,
        DV_OFFLINE=dv_ol, DU_OFFLINE=du_ol, DR_OFFLINE=dr_ol,
        DV_SZH=dv, DU_SZH=du, DR_SZH=dr,
        PER_CASE='\n'.join(per_case_rows),
        G1=f"{pct(v_g1)} / {pct(u_g1)} / {pct(r_g1)}",
        G2=f"{pct(v_g2)} / {pct(u_g2)} / {pct(r_g2)}",
        G3=f"{pct(v_g3)} / {pct(u_g3)} / {pct(r_g3)}",
        G4_SMOKE=f"{pct(v_fs)} / {pct(u_fs)} / {pct(r_fs)}",
        G4_DEV=f"{pct(v_fd)} / {pct(u_fd)} / {pct(r_fd)}",
        G4_TEST=f"{pct(v_f)} / {pct(u_f)} / {pct(r_f)}",
        AUDIT_N='12,156（8 个运行全部重放）',
    )
    out = out.replace('本文档是本任务唯一的实验结果与数据文档（占位数字以 `{{...}}` 标记，运行完成后填入）。\n', '本文档是本任务唯一的实验结果与数据文档。\n')
    (ROOT / 'docs' / 'experiment-results-3d.md').write_text(out, encoding='utf-8')
    print('filled docs/experiment-results-3d.md')


if __name__ == '__main__':
    main()
