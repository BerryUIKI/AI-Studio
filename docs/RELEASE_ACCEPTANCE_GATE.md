# Current-head release acceptance gate

`Release Acceptance / Current-head Release Acceptance` runs for every PR targeting
`main`, including changes to its evidence reference. Missing evidence fails the job.
Feature and integration PRs targeting `dev` do not need live acceptance artifacts.
This workflow verifies evidence; it does not merge, publish, tag or promote a release.

The testing agent runs the approved live and clean Windows journeys on the exact
release candidate SHA. Keep the handover and evidence bundle outside Git. Upload
the reviewed bundle as a GitHub Actions artifact in a successful, same-repository
run on that SHA. The artifact contains `evidence.json` at its root and all referenced
nonempty output/diagnostic files at relative paths. Use `actions/upload-artifact@v4`
in the authorized test workflow; do not put secrets in the artifact.

Reference the run and artifact in the release PR body:

```text
<!-- berry-acceptance {"run_id":123456789,"artifact":"release-acceptance"} -->
```

The gate checks the source run's repository, successful conclusion and exact PR
head before downloading. `scripts/verify-release-evidence.py` then requires all
R01–R18, L01–L12 and named release scenarios, current commit/environment/integration
metadata, live evidence levels and actual artifact files. L01, L12 and the clean
Windows package scenario require packaged-live evidence. R17 may use portable CI.
Mock-only, historical, absent and wrong-commit evidence fails. Changing code invalidates
the reference until the affected acceptance is rerun for the new head.

Evidence completeness does not prove the content's truth. Product-owner review of
the artifacts and release approval remain required under the branching policy.
The repository administrator should make this named job a required `main` status
check. The workflow itself always fails missing evidence, but branch protection is
the server setting that prevents a privileged merge from bypassing a failed job.
No branch-protection permissions or release publication are changed by this PR.
