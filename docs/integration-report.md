# Stage integration audit

Base: origin/main 717c896. Integrated origin/jcj129321/coverage-guided using a real merge; the sole conflict was README.md. Main content was retained and JCJ entry/results added. No LWT branch was merged or modified.

Canonical methods: szh-baseline-causal-task-a, szh-baseline-3d-task-b (original/adapted), szh-baseline-genetic-task-c, szh-baseline-common, jcj-coverage-guided-task-b, zjh-spatial-task-b.

Formal configurations, numerical results, request/response archives, checksum inventories and figures are retained byte-for-byte. integration-preservation.json records old/new locations and SHA256. Historical path strings inside immutable results remain unchanged. Operational script/import/doc paths are updated; legacy Python entry points execute one canonical implementation. Frozen A/C code retains its original source hashes and uses runtime path translation.

Validation: 21 root tests (including nine JCJ tests), five ZJH tests; compile checks; Original 585 and Adapted 585 request/hash/score replays; A 2,019 and C 270 complete replays; archive restoration verified. No new inference. JCJ's 585 SHA256 inventory and submitted result/report are preserved; raw responses are not in this repository and independent per-call replay is not verified, as explicitly accepted by the owner. ZJH original submitted audits and metrics are preserved; no unavailable raw data are fabricated.

Read the method READMEs for current commands. Re-run: python experiments/audit_integration.py; python experiments/audit_all_domains.py --domain causal; python experiments/audit_all_domains.py --domain genetic. Use python experiments/run_domain.py for new A/C inference, and the original/run.py or adapted/run.py entries under the 3D method for new 3D inference. Integration does not change experiment parameters or recompute published measurements.
