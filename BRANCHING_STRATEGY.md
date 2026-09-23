# Berry AI Studio GitFlow Branching and Release Policy

Status: project policy. All branch names, commit messages, pull requests, tags, and release notes use English.

## 1. Permanent Branches

| Branch | Purpose | Rules |
| --- | --- | --- |
| `main` | Released, production-ready history | Protected. No direct commits or pushes. Release and hotfix PRs only. Every new release commit is tagged after merge and verification. |
| `dev` | Integration for the next release | Protected. Feature and ordinary bug-fix PRs merge here. A green `dev` build is integration evidence, not a release declaration. |

Do not use `main` as a working branch. Do not tag a feature branch or `dev` as an official release.

## 2. Short-Lived Branches

| Pattern | Create from | Merge into | Purpose |
| --- | --- | --- | --- |
| `feature/<issue-or-topic>` | `dev` | `dev` | New product capability or focused technical work. |
| `bugfix/<issue-or-topic>` | `dev` | `dev` | Ordinary defects found during development. |
| `docs/<issue-or-topic>` | `dev` | `dev` | Documentation-only changes. |
| `release/vX.Y.Z` | `dev` | `main`, then synchronize back to `dev` | Release stabilization, version numbers, changelog and packaging fixes. |
| `hotfix/vX.Y.Z` | `main` | `main`, then synchronize back to `dev` | Urgent correction to a released version. |

Use lowercase, short, descriptive names. Include an issue ID when one exists. One branch should have a reviewable objective; avoid accumulating unrelated milestones in one branch. Existing historical branches are not renamed merely to satisfy this policy.

## 3. Normal Development Flow

1. Update local `dev` from `origin/dev` and create a short-lived branch from it.
2. Implement a focused change with the relevant tests and English documentation.
3. Write English Conventional Commits, for example `feat(launcher): add startup readiness check` or `fix(runtime): preserve engine data during update`.
4. Open a PR targeting `dev`. Describe user-visible behavior, validation evidence, limitations and related requirement or issue IDs.
5. Keep the branch current with `dev` before merging. Resolve conflicts on the working branch and rerun affected checks.
6. Merge only after review and required checks pass. Prefer squash merge for feature, bug-fix and documentation PRs, yielding one clear change in `dev` per PR. Delete the temporary branch after merge.

Never merge a feature branch directly into `main`. Never force-push a shared integration or release branch. Rebasing a personal branch before review is allowed; do not rewrite a shared branch after others depend on it.

## 4. Release Flow

1. Once the planned scope is integrated in `dev`, create `release/vX.Y.Z` from the current `dev` commit. No new features enter the release branch.
2. On the release branch, allow only regression fixes, version/changelog updates, packaging, security fixes and release documentation. Record the exact commit and test environment for the release candidate.
3. Run the complete release gate: required CI, Windows package installation and launcher checks, supported local/cloud creation journeys, update/recovery tests, and documented open limitations. Mock tests alone do not establish real engine or provider compatibility.
4. Open a PR from `release/vX.Y.Z` to `main`. Merge with a merge commit to preserve the release branch and the verified release candidate. Do not squash a release PR into unverified contents.
5. Verify the resulting `main` commit and create an annotated tag `vX.Y.Z` on that commit. Publish artifacts and release notes from the tagged commit only. Publishing is a separate release action.
6. Synchronize the released changes back into `dev` using a PR from `main` (or an equivalent reviewed back-merge that preserves the release commit). Resolve any conflicts and run affected checks. Then delete the release branch.

If a release fix must also reach ongoing development before the final back-merge, apply it through a separate reviewed PR or wait for the back-merge. Do not silently cherry-pick the same change twice.

## 5. Hotfix Flow

1. Create `hotfix/vX.Y.Z` from the current `main` release tag or commit, not from `dev`.
2. Make the smallest correction needed. Add a regression test when it verifies the failure. Update version and release notes.
3. Run targeted checks plus affected release smoke tests. Open a PR to `main` and merge with a merge commit after review.
4. Tag the merged `main` commit with the patch version and publish artifacts from that tag.
5. Back-merge `main` to `dev` through a reviewed PR. If a release branch is open, also synchronize the hotfix into that release branch and resolve conflicts before release.

## 6. Versioning and Tags

Use SemVer tags in the form `vMAJOR.MINOR.PATCH`. Increment major for incompatible public project/workflow formats or APIs, minor for compatible features, and patch for compatible fixes. Before a public 1.0 release, explain any compatibility breaks in release notes even when SemVer allows flexibility.

The repository may contain historical commits without release tags. This policy governs future releases; do not create retrospective tags without matching verified artifacts and a documented reason.

## 7. Protection, Review and Checks

Configure repository branch protection for `main` and `dev`: no direct pushes, required status checks, and up-to-date PR branches.

- **Merging into `dev`**: Feature, bug-fix, and documentation pull requests targeting `dev` may be self-merged once all required automated checks pass and the PR checklist is fulfilled. Failing checks must never be bypassed.
- **Promotion to `main`**: Release (`release/vX.Y.Z`) and hotfix (`hotfix/vX.Y.Z`) pull requests targeting `main` strictly require product-owner release approval and verified release evidence before publication.

At minimum, gate changes with the checks that exist and are relevant: backend tests, frontend type-check/build, Rust launcher build/tests, formatting/lint where configured, and a documentation/link check. Add CI workflows for these gates if missing. Real Windows packaging, local engines, cloud providers and hardware need recorded manual/integration evidence at release time; mark unavailable checks unverified rather than passed.

Never commit secrets, model weights, generated assets, local runtime directories, or build outputs unless a reviewed packaging requirement explicitly calls for a generated artifact. Keep application and engine update changes separate where possible.

## 8. Current Large Feature Branch

`feature/berry-product-alignment` currently holds reported M0–M6 implementation. Treat its completion reports as developer evidence awaiting unified acceptance. Do not merge it into `main` or tag a release directly.

Before integrating it into `dev`, prepare a PR with a change summary by requirement, current test/build results, known limitations, and a separate list of real Windows, local-engine and cloud scenarios that remain unverified. Review the diff for unrelated changes and split follow-up work into focused branches where practical. If the branch cannot be split safely after shared commits, integrate it as one reviewed exception and return to small branches afterward. Unified product acceptance and release promotion remain separate decisions.
