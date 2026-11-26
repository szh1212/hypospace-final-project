# Task-oriented layout verification

Base main: 15e604a. All six method directories were moved with git mv into task-a, task-b, task-c and common. Frozen top-level A/C sources and scientific configurations/results were not edited. Shared transport, CLI launchers, path routing and the reusable 3D framework have one implementation under common/szh-baseline-common; old entry points are compatibility wrappers.

Validation: 23 root tests (including two path-routing regressions), five ZJH tests, and the nine JCJ tests also run independently. Available archived requests were independently replayed: A 2,019, C 270, 3D Original 585 and Adapted 585. All hashes, requests and scores match. No formal inference was run. JCJ raw responses remain unavailable and are not claimed as independently replayed; submitted reports/manifests are preserved. No LWT branch or method was handled.

Task/method README local links were checked with no broken targets. Main README edits are directory-tree and path/link updates only. The immutable-artifact manifest records pre-move Git SHA256 values and new paths; staged Git blobs were compared with these original values before publication.
