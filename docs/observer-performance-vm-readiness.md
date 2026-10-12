# Observer Performance and course lifecycle: VM readiness

Reviewed: 12 October 2026. Branch: `codex/observer-performance-parity`.

**Ready for coding-VM integration testing.** Deploy the exact latest committed revision of this branch to the coding VM first. Record the commit and image versions that pass there; use those same versions for on-prem UAT. This review did not push or deploy to either environment.

## Checks completed locally

- Backend full regression: 356 passed, 72 explicit integration skips, one existing image-slide assertion failure reproduced in the original checkout.
- Real PostgreSQL: 68 passed across lifecycle, completed learning/history preservation, rule snapshots, migration idempotence, stale/concurrent writes, one-connection pool behavior, grant/identity boundaries, content/media restrictions, course-library pagination and seeded report totals/search/sort parity.
- Trainer Flutter tests: 44 passed. Employee focused tests: 21 passed.
- Both web clients compile with the Dockerfile build flags and Flutter 3.44.0; dependency lockfiles are unchanged.
- The follow-up fixes cover legacy withdrawn-assignment totals and lifecycle database-pool exhaustion.

## Coding-VM acceptance checklist

1. Take a database and LMS storage backup before updating the existing VM. Upgrade through normal backend startup, which applies the additive lifecycle migration. **Do not run `recreate_lms_database` or `seed_performance_demo` on the VM.** Those reset/seed workflows are not part of this upgrade.
2. Rebuild and deploy backend, Trainer and Employee services from the same commit. Check Docker build output, service health and backend startup logs. Confirm `20261009_course_lifecycle_v1` is recorded once, retained assignment/module counts are unchanged, and a second restart is clean. Record an available backup/previous-version recovery path.
3. Keep `EMAIL_DELIVERY_MODE=disabled` while testing, and use normal Hub sessions with `HUB_LAUNCH_DEV_MODE=false`. Limit course assignment tests to controlled test accounts.
4. Test Trainer and Employee URLs through the VM's actual proxy/mount paths. Exercise searchable Course/Department/Mailing list filters, employee debounce/clearing, course pagination, mobile-width layout, details and CSV exports. Compare visible totals with exported rows.
5. Test role boundaries using a normal Trainer, a different course creator/Admin Trainer, an Observer, a HOD and a person who is both HOD and Observer. Combined must contain the union once; removing Observer access must leave only independent HOD-authorized rows. Suspended/revoked Observers must not regain access through All/Disabled/Archived filters or saved report URLs.
6. Exercise Publish & Assign → Update Assignments → Exclude unfinished and completed employees → Disable → Enable → Archive → Restore → Disabled → Enable → Apply Observers. Check that Save Rule alone does not change enrollment; Restore/Enable alone do not activate Observers; scores, answers, attempts, completion dates and deadlines survive. Check unused Delete/DELETE confirmation and rejection of deleting any assigned course.
7. Try saved learner/video URLs and progress requests after exclusion, Disable and Archive. Access must be denied even for completed employees. Check stale tabs/concurrent actions give a refresh/conflict response rather than applying stale changes. Check generation cannot reopen an Archived course.
8. Confirm generation, playback and directory sync still work under the VM's integrations. Review the existing landscape-image slide test failure and the video-player analyzer finding separately. Record whether each is resolved or accepted as a known issue; this branch's successful web compilation does not make the whole regression/analyzer run clean.

## Gate before on-prem UAT

Complete and record the VM checks above with no unresolved new blocking defects. The local Chrome app-shell smoke test stalled while loading, so live authenticated UI/proxy testing is still required. Then promote the exact VM-tested revision/images to on-prem UAT, with that environment's backup and migration/startup checks. On-prem production approval is outside this testing rollout.
