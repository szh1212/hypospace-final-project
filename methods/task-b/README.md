# Task B: 3D Voxel Reconstruction

Existing methods:

- [szh-baseline-3d](szh-baseline-3d/README.md)
- [jcj-coverage-guided](jcj-coverage-guided/README.md)
- [zjh-spatial](zjh-spatial/README.md)
- [kevin-twolevel-stratification](kevin-twolevel-stratification/README.md)

Published formal results (macro averages; no new inference):

| Method | Validity | Uniqueness | Recovery | Calls |
| --- | ---: | ---: | ---: | ---: |
| Original | 0.00% | 55.56% | 0.00% | 585 |
| Adapted | 78.52% | 21.65% | 17.45% | 585 |
| JCJ coverage-guided | 77.86% | 25.27% | 21.89% | 585 |
| ZJH codec | 100.00% | 61.73% | 61.73% | 585 |
| ZJH layers | 44.69% | 32.84% | 17.70% | 585 |
| Kevin two-level stratification | 100.00% | 95.97% | 95.97% | 585 |

Protocols differ; compare methods only under matched cases, seeds and budgets. Exact configurations, per-instance scores and archive availability are documented in each method.
Both SZH 585-call raw archives are included. JCJ raw responses are not included; its submitted report and 585-file SHA256 inventory are preserved without claiming independent historical replay. ZJH retains both published variants and submitted audit reports. Kevin two-level stratification is paired on the SZH cases, seeds and budget; its 585-call raw archive is local-only with a SHA256 inventory, and all 2,145 records were replayed by its offline audit.
