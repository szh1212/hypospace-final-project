# Contributing

All four teammates use the same workflow: create a personal task branch from the latest `main`, submit a pull request, and have another teammate review and approve it before merging. Do not push project changes directly to `main` after initialization or approve your own PR.

## Clone and create a branch

After accepting your collaborator invitation:

```sh
git clone https://github.com/szh1212/hypospace-final-project.git
cd hypospace-final-project
git switch main
git pull --ff-only origin main
git switch -c yourname/task-description
```

Replace `yourname/task-description` with a unique branch such as `alice/baseline-plan`. Create a new branch from updated `main` for each task; do not share a working branch across teammates.

## Commit and open a PR

Stage specific intended files and inspect the staged changes before committing:

```sh
git status --short
git add docs/project-plan.md
git diff --cached
git commit -m "docs: claim baseline planning task"
git push -u origin yourname/task-description
```

On GitHub, open a pull request from your branch into `main`. Describe the goal, changes, and checks performed. Link the claimed task or issue, and explicitly state when experiments have not been run. Keep PRs small and focused.

Request review from one of the other three teammates. The reviewer checks correctness, scope, reproducibility, and the absence of secrets or large artifacts. Address feedback, obtain at least one approval from someone other than the author, and then merge using GitHub's Squash and merge option. Delete the merged branch on GitHub and update local `main` before starting new work.

If a branch conflicts with `main`, merge the latest `origin/main` into the task branch, resolve conflicts, and request review again for substantive changes. Never force-push `main`.

## Ownership and coordination

- Claim one starting task in [docs/project-plan.md](docs/project-plan.md) by adding your GitHub username in a PR. Coordinate claims to avoid duplicate ownership.
- Each member owns a task and reviews another member's work. Discuss interfaces and shared files before editing them concurrently.
- Record decisions and short experiment summaries in `docs/`. Keep configurations and launch scripts in `experiments/`, and our method implementation in `src/`.
- The owner has authorized baseline implementation and offline verification. Shared protocol is in methods/szh-baseline-3d-task-b/docs/baseline-protocol.md; local zero-cost Qwen/Ollama execution is authorized; formal experiments wait for the failed smoke quality gate to be resolved.
- Never commit API keys, personal files, model weights, datasets, or raw experiment outputs. `.gitignore` is a convenience, not a substitute for reviewing the staged diff.

## Repository owner setup

Invite the other three members through **Settings → Collaborators → Add people**. After invitations are accepted, use GitHub's branch protection or rulesets settings to protect `main`: require a pull request, at least one approving review, and dismissal of stale approvals after new commits. Block force pushes and deletion. Apply the rule to administrators where supported. These settings must be configured on GitHub; this document alone does not enforce them.
