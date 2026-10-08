# Combined LMS feature and SBOM release implementation plan

Prepared 8 October 2026. This is the implementation sequence for integrating verified candidate security changes with the latest application release. It supersedes the starting sequence in the earlier operations plan.

## Starting position

- Local SBOM branch: `codex/lms-sbom-remediation`, based on `16adda05f58ca0a6babbd2f3b1a6e621c4a5e3f3` (1 October). Security implementation changes are uncommitted, with required untracked build inputs and assets.
- Locally cached `origin/main` is `1b734ab` (7 October); this is not proof of today's remote main or running deployment revision. The other session recorded feature commits `6aa5b7b` and `7402617`. Verify their integration into current main and the actual deployment before choosing a base.
- Candidate security evidence was generated on big-coding; it does not certify the current live application. Earlier candidate images were deleted during cleanup.
- Preserve latest trainer visibility, Performance, Observer, assignment, SMTP and shared-route behavior.
- Scope: backend, trainer frontend and employee frontend. PostgreSQL security remediation remains deferred. The failed PDF source replacement is excluded.
- Historical active scope: 612 of 873 tracked occurrences addressed; 261 inherited entries remain open (6 High, 40 Medium, 195 Low, 20 Unknown). Refresh counts for the combined images; do not claim historical candidate results as current deployment results.

## Step 1 — Establish and preserve the baseline

Read current Git main and record source/image identities for the running big-coding deployment; record UAT identities when accessible. Verify whether the recent feature commits are merged and deployed. Retain both facts separately: repository state is not runtime state.

Preserve the local SBOM tracked diff plus explicitly selected untracked security scripts, locks, fonts and licence files in a recoverable snapshot with checksums. Do not stash, reset, clean, switch the dirty checkout, or overwrite another session's changes. Archive experimental evidence separately; omit secrets, caches, environments and unrelated feature files.

Completion: baseline record, recoverable SBOM snapshot and explicit release file list. Current deployed features cannot silently disappear from the release base.

## Step 2 — Integrate on the current feature base locally

Use a separate checkout/worktree on a `codex/` integration branch based on verified current main. If recent required feature commits are not merged, identify the intended combined base explicitly rather than silently dropping or merging them. Apply only the selected SBOM implementation changes. Resolve changes semantically, especially:

| Integration area | Required behavior |
| --- | --- |
| Backend Dockerfile | Full maintained security runtime, current application source and required build inputs. Do not select an older intermediate Docker stage. |
| Frontend Dockerfiles | Security SDK/lock/font settings plus latest Nginx template and trusted-edge configuration. |
| Python and Flutter locks | Preserve feature-required packages while retaining security pins; regenerate only when integration requires it. |
| Compose and overlays | Preserve latest environment variables, routes, storage, service names and both `lms.pr-onprem.yml` and `lms.edge-network.yml` settings. Add security restrictions without losing edge aliases. |
| Database | Preserve the deployed database reference/configuration; do not deploy the historical PostgreSQL candidate. Review feature-related startup migrations independently. |

The existing SBOM Compose diff adds app-service security restrictions; it does not itself change the PostgreSQL image reference. Compare the final effective configuration against each deployment, because the running database may differ from repository configuration.

Completion: focused combined diff, recorded integration commit and reviewed build/deployment configuration. Exclude the failed PDF replacement. No production service changes at this step.

## Step 3 — Verify the combined source

Run backend checks relevant to authorization, reporting, assignments/Observer separation, deadlines, SMTP and Hub routing. Run the latest trainer Performance/assignment tests, employee checks and release builds under the chosen SDK. The other session's 36 passing trainer tests are historical; rerun the current combined suite.

Preserve access boundaries: visibility does not imply edit/delete permission, and reporting access does not imply learner assignment. Include these negative permission cases in validation. Resolve essential regressions before building a release candidate.

Completion: recorded test/build results for the combined commit. Findings left open keep their existing status.

## Step 4 — Rebuild and scan on big-coding

Transfer the recorded combined source into an isolated VM workspace. Rebuild backend and both frontends using explicit targets and deployment-appropriate build arguments. Record commit, input hashes, logs and image identities. Investigate native guard drift before changing its baseline; a new hash is not security approval.

Scan all final image identities with recorded scanner/database metadata, generate SBOMs, validate their format and package/licence coverage, and refresh the assessment. Use the same database snapshot for comparisons when possible. Treat newly introduced unacceptable reachable Critical/High vulnerabilities as blockers; retain unresolved coverage assessments and prepare owner decisions rather than silently suppressing them.

Completion: three complete candidate images with SBOMs, raw scans, assessments and checksums. No deployment from the old SBOM branch or historical image tags.

## Step 5 — Test the candidate workflows on big-coding

Start with isolated test data/storage, a dedicated test database, separate project/ports and safe notification settings. Do not attach candidate tests to the live database/storage by default. Disable scheduled sends/directory synchronization for synthetic validation. Actual external email requires explicit authorized recipients.

Validate the following against the combined candidate:

- Real Hub trainer/employee launch and direct/shared URL routing, cookies and private-media authorization; preserve edge network aliases and avoid the previously observed 502.
- Cross-trainer course visibility and authorized Performance reporting, including unauthorized denial cases.
- Course/department/mailing-list search, employee search, pagination and current report values.
- Observer search and Select all/Clear all; learner/Observer separation; saving/applying scope.
- New Specific-date deadline default with existing saved deadlines preserved; publish/assignment counts and refresh behavior.
- PDF/document extraction, slides, narration, video generation, HLS playback, completion/progress and notification previews.

Record disposition for the historical slide-layout mismatch and employee browser-test gap. Use a separate controlled test route/network for Hub acceptance before promoting into normal routes; connecting candidate containers must not replace live aliases accidentally.

Completion: essential workflow results, logs/screenshots, runtime identities and evaluated residual risks. If normal-route big-coding rollout is needed, record rollback images/configuration first and recreate only the selected app services with both overlays.

## Step 6 — Review the release and promote to UAT

Prepare the focused PR and release evidence bundle after validation. Record required residual-risk decisions, owners and review dates. PostgreSQL remains deferred; the six inherited High coverage reviews are not automatically accepted. Preserve previous app images, effective configuration, and backup/restore readiness. Check migration compatibility: rolling back images alone cannot undo database writes or schema changes.

After the required release/deployment decision, promote the exact tested app images to `10.204.6.139` through a registry or checked image archive. Match the effective frontend API configuration to UAT; if build-time values force a separate frontend build, identify it as a different artifact and validate it separately. A main-branch pull or identical tag name is insufficient proof of identical images.

Recreate only scoped application services; preserve the database and edge configuration. Repeat essential UAT acceptance checks and verify running image identities. Roll back on an essential regression using the prepared procedure.

Completion: verified UAT release, matched artifact identities, final evidence and owned backlog. No blanket whole-platform security clearance is claimed.

## Next action and progress

Planning is complete. Step 1 is next: confirm current main and deployment identities, then preserve the SBOM changes. No integration, fresh build, scan or deployment has been performed by creating this plan.
