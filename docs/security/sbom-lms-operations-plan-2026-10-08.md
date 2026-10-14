# LMS operational release plan — 8 October 2026

Move from broad remediation to release preparation and validation. This plan does not approve residual risks or certify the running deployments. Historical candidate scan results must be refreshed after rebuilding.

The [combined release implementation plan](sbom-lms-combined-release-implementation-plan-2026-10-08.md) supersedes the starting sequence below: preserve the dirty SBOM checkout and integrate its selected changes on verified current feature code before building.

## Scope selected for preparation

- Backend, trainer frontend and employee frontend, using the completed maintained security changes.
- Retain the existing PDF dependency for this release preparation. Exclude the failed PyMuPDF/MuPDF source replacement and its experimental build inputs from the release implementation. Preserve its evidence separately.
- PostgreSQL security remediation and database image changes remain deferred. The SBOM Compose diff adds app-service restrictions and does not change the database image reference. Preserve the existing approved deployment reference/configuration when preparing the combined release. Do not start the bundled database profile against existing data during candidate tests.
- Preserve the remaining risk register: 6 High, 40 Medium, 195 Low and 20 Unknown inherited backend entries. No entry becomes fixed or accepted by moving to operations.
- Include only LMS security implementation files and release evidence in the focused review. Unrelated local feature plans, temporary outputs, environment files and failed experiments are outside the release bundle.

## Execution sequence

| Step | Operation | Required output / gate |
| --- | --- | --- |
| 1 | Review the release diff and create a reproducible source snapshot | Exact commit or archived source hash; explicit build targets/arguments; release scope; residual-risk review draft. Preparation scope selected here; code review and risk decisions remain pending. |
| 2 | Rebuild all three app images on big-coding in an isolated workspace | Build logs, image IDs, dependency provenance and native guard results. Select the full maintained backend target, not an earlier intermediate stage. Investigate hash drift before updating the native lock. |
| 3 | Scan the exact rebuilt images and generate final SBOMs | Scanner image and vulnerability database metadata; image-linked raw reports, assessments, SBOMs and checksums. Review new Critical/High matches and retain historical coverage gaps. |
| 4 | Run isolated backend and full-stack checks | Dedicated test database/storage and loopback test ports; email delivery disabled or captured locally; scheduled jobs/directory sync disabled for synthetic tests. Successful health, parser/native and application workflow checks. |
| 5 | Validate real Hub workflows on big-coding using designated test accounts | Trainer and employee login, access controls, course creation/assignment, PDF/slides, narration/video generation, HLS playback, progress/completion and notification previews. Actual email sends only to explicitly authorized test recipients. Resolve essential failures, including the known slide-layout mismatch and employee browser-test gap. |
| 6 | Prepare the release and rollback bundle | Focused reviewed source changes; exact tested images; SBOM/scan reports; test results; risk dispositions with owners/review dates; deployment manifest; backup/restore and rollback procedure. Required risk/release decisions must be recorded before UAT promotion. |
| 7 | Promote to UAT at 10.204.6.139 | Transfer the tested images through an accessible registry or image archive with checksums. Verify image identity on UAT; deploy only the three app services with the existing database configuration. Preserve prior images/configuration and assess any startup migrations before rollout. |
| 8 | Verify UAT and hand over | Repeat essential smoke workflows, check health/logs and confirm running image IDs. Roll back on an essential failure. Deliver the final SBOM, evidence bundle and owned residual backlog. |

## Deployment safeguards

Record existing app image IDs, Compose project/service identities, effective configuration locations and storage mounts before changes. Keep credentials out of reports. Confirm database backup and restoration readiness before a rollout that can write or migrate data; an image rollback alone cannot reverse a database migration.

Using the same Git main branch on two machines does not prove identical images. Prefer promoting the tested artifacts. If UAT must rebuild, identify it as a separate candidate and repeat scans and validation there.

Do not use a broad Compose restart or database recreation for this scoped release. Test Compose configuration without printing resolved secrets. Prepare a dedicated override/deployment manifest before starting services.

## Current checkpoint

Operations plan prepared; no rebuild, scan, application restart or deployment was performed in this planning step. The next execution task is the focused source/configuration review and release snapshot, followed by the three isolated image builds. Residual decisions remain pending, and PostgreSQL is explicitly deferred.

After release, maintain scans for new releases and review the residual backlog periodically. No recurring automation is created by this plan.
