# Causal graph adapted baseline

Status: COMPLETE for formal inference and local replay; LWT values are cited from its formal report (Historical Replay Not Verified). Shared implementation, protocol, prompt and commands are in ../szh-baseline-common/. Raw archive: runs/all-domains/causal/. Reports will be written to reports/ only from real runs.

Model and sampling remain identical to the frozen 3D adapted baseline. The separate aligned protocol uses LWT final test identities and prefix budgets 4/8/13/16; its 256-token GPU setup differs from our 512-token CPU setup and must be disclosed in comparisons. LWT raw prefix verification remains pending until its raw archive is available.
