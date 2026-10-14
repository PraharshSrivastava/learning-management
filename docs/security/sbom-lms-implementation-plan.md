# LMS SBOM implementation plan

Prepared: 5 October 2026. Execution model: one maintainer working with Codex.

Scope update: PostgreSQL security fixes are deferred by user instruction on 6 October. Continue with backend and both frontends. Preserve already completed PostgreSQL candidate/evidence separately; do not include it in active release totals, further tests, or deployment. The additional PostgreSQL Compose hardening was removed.
Status, updated 7 October after consolidated backend round5: one inherited High and 38 Medium occurrences addressed; 6 High and 59 Medium remain open. Raw scan: 0 Critical, 0 High, 27 Medium, 12 Low. Native/application checks passed except the known layout test. Source/private provenance, supported fixes, full rebuild and real Hub/full-stack release gates remain open. Backend remains active; PostgreSQL stays deferred. See [round-five evidence](sbom-lms-backend-remediation-round5-2026-10-07.md).

## Outcome

Establish what software the LMS actually contains, verify which reported vulnerabilities still apply, fix actionable risks without breaking course generation or learning, and retain repeatable evidence for future releases.

## Execution optimization â€” 6 October 2026

Re-read the saved backend candidate 03 report before selecting further upgrades. All 829 remaining occurrences are Debian findings; the Python and Node result sections contain zero reported findings. None of the remaining Debian occurrences has a populated FixedVersion in the saved 5 October advisory snapshot. This does not establish that no fix exists today or that those issues are harmless. The 829 occurrences represent 335 distinct advisory IDs across packages.

FFmpeg and eight related libav/libsw/libpostproc packages account for 279 occurrences, including 144 high occurrences. Treat them as a shared remediation investigation rather than 279 independent tasks. The critical libxml2 occurrence remains an explicit priority because the backend processes documents.

Use the following shorter execution loop for the remaining work:

1. Refresh advisory results once for the exact existing candidate images, preserving the original reports and database metadata. Keep the original same-database before/after comparison separate from the refreshed risk view. Group findings by source package/family and classify supported fix, no listed fix, removal candidate, or applicability investigation.
2. Complete both frontend candidates as one batch because they share runtime definitions. Build each application separately and preserve separate image IDs, scans, and serving checks. Assess Dart coverage explicitly.
3. Review backend OS findings by family, starting with libxml2 and FFmpeg. Check supported fixes and actual usage before editing. Do not repeat Python upgrades solely to reduce Debian counts. Do not remove required media/document tools or replace the distribution without a compatibility reason.
4. Make one candidate build and scan per coherent change batch; run the relevant existing checks once. Repeat only after changes or failures. Preserve untouched PostgreSQL evidence rather than rerunning database tests for unrelated frontend/backend edits.
5. Run a consolidated full-stack Hub/UI validation after the candidate set is ready, then prepare release/rollback artifacts. Deployment remains separately authorized and findings close in a deployed environment only after running-image verification.

Generate inventories, grouped reports, and counts from JSON rather than manually reviewing every occurrence or editing workbook rows. Keep unfixed issues visible with exposure, mitigation, owner, and review trigger; lack of a listed fix does not automatically satisfy the release gate. Time-box investigations that produce no change in the next decision, but continue any investigation needed to resolve a release blocker. The subsequent gosu rebuild was completed with immutable source, patched Go/x/sys, binary auditing and startup/transaction/backup/restart tests; preserve those checks when maintaining this custom artifact.

Local analysis evidence: ignored `tmp/sbom-candidate/backend-candidate-03.json` and `backend-remaining-findings.csv`. These are saved-report analyses, not a fresh scan. The original eight-phase plan below retains its scope and release requirements; this section changes execution order and batching.

Work through one numbered step at a time. At the end of each step, record the result, evidence, unresolved items, and next step here. A prerequisite failure leaves dependent work pending; it must not be presented as a successful scan or test. Source inspection and report triage can continue while Docker is unavailable.

## Starting evidence and observations

- Source workbook: `C:/Users/LPUSER/Downloads/SBOM-ai-assistant-lms.xlsx`, assembled 30 September 2026. Preserve the original. Its Vulnerabilities sheet reports an OSV query; its SBOM and Summary findings still say no scan was supplied. Treat this as an evidence inconsistency to reconcile.
- Prior workbook analysis counted 230 LMS advisory occurrences: 30 critical, 100 high, 83 medium, 12 low, and 5 unrated. It counted 156 distinct advisory IDs and four redundant identical rows. Reproduce these counts in step 2. Advisory IDs and affected-image occurrences are different metrics.
- Repository inspected at commit `16adda0`. Existing untracked `docs/admin-trainer-implementation-plan.md` and `tts-openapi.json` are unrelated; preserve them.
- The current backend, frontend build/runtime, and optional PostgreSQL definitions already specify images pinned by digest. Current frontend Dockerfiles use Ubuntu 24.04 and nginx 1.31.6/Alpine 3.24 rather than the older workbook images. Image references are observed configuration, not fresh verification of registry availability or deployed contents.
- Both frontend Dockerfiles run `apk upgrade`. Backend OS packages and browser dependencies are downloaded during builds. A pinned base alone does not make the entire build reproducible; capture final image identifiers and installed inventories.
- Both frontends disable Google Fonts runtime fetching and declare bundled font assets. Verify offline rendering instead of automatically implementing the historical font finding again.
- Backend code actively uses PyMuPDF, Playwright, and imageio-ffmpeg. Do not remove them as unused dependencies without checking the affected functionality. Inventory the system FFmpeg and bundled FFmpeg separately.
- `docs/security/vapt-2026-09-25.md` records earlier fixes, scan results, and an image-slide test failure. These are historical evidence, not current pass results. Its large image counts are not directly comparable to the workbook's counts.
- Docker CLI is installed, but the Docker Desktop Linux engine was unreachable during inspection. Trivy, Syft, Grype, and Flutter were not found on PATH; this does not prove they are absent from every local environment.

## Step 1 â€” Confirm scope and prepare a safe local environment

Actions:

1. Record the checkout commit, worktree status, application architecture, and current dependency/build files. Establish an isolated branch before implementation and preserve unrelated changes.
2. Ask whether the live LMS runs this checkout and whether production is online or offline. Record deployment access and live image identifiers if available; otherwise label production status unknown.
3. Confirm Docker Desktop can run Linux containers and identify available Python/test and Flutter runtimes. Check existing tool locations before adding tools. Prefer one primary image scanner, Trivy, rather than installing several scanners initially.
4. Prepare a separate local database and storage directory with synthetic fixtures. Configure email delivery and directory sync off and avoid production credentials, employee records, and live provider requests during ordinary tests.
5. Keep raw scan evidence in a local ignored directory such as `tmp/security-evidence/<run-id>/`. Keep redacted summaries and the plan under `docs/security/`.

Deliverable: environment checklist and build/test instructions, with missing prerequisites clearly identified.

Exit check: local paths and service configuration are understood; Docker works before image work starts; test data and side effects are isolated. Production access is not required for local validation, but it is required to claim live remediation.

Problem addressed: analyzing the wrong build or accidentally operating on live data.

## Step 2 â€” Normalize and validate the Excel findings

Actions:

1. Extract LMS rows with original sheet/row references. Preserve the supplied finding, severity, installed version, and listed fixes separately from our decisions.
2. Remove redundant identical records from actionable counts while retaining provenance. Group shared remediation work across the administrator and employee images; preserve both affected targets.
3. Check suspicious installed-version/fixed-version matches, advisory aliases, missing descriptions, and Debian/Alpine branch applicability against authoritative advisory data.
4. Map workbook components to current Dockerfiles, lockfiles, and the prior VAPT review. Mark previously changed items as awaiting verification, not automatically closed.
5. Create a tracker with target, package/ecosystem, installed version, advisory, source row, supplied severity, validation status, exposure, planned action, owner, target date, and evidence. The maintainer is the owner; Codex assists with analysis and implementation.

Deliverable: LMS findings tracker and reconciliation summary. Select specific dates after validation rather than treating historical workbook windows as new deadlines.

Exit check: counts reconcile, provenance is retained, and questionable findings are identified. Unverified entries remain pending validation.

Problem addressed: duplicate work, misleading counts, and incorrect upgrade recommendations.

## Step 3 â€” Capture a fresh build and scan baseline

Actions:

1. Build the current backend and both frontend runtime images with recorded build arguments. Identify and scan the optional PostgreSQL image, or document the separately managed database's scope.
2. Record source commit, build time, platform, base digests, final local image IDs or registry digests, scanner version, vulnerability database metadata, and commands. Do not publish raw credentials or resolved secret-bearing Compose configuration.
3. Scan the final runtime images, not just their declared bases. Include findings without fixes and unrated findings. Scan build stages separately and label build-only risks separately from runtime risks.
4. Audit the exact Python lockfile and inventory both Dart lockfiles. Confirm scanner support before claiming Dart vulnerability coverage; use ecosystem/advisory checks and record gaps where automated support is incomplete.
5. Record the installed Chromium version, system FFmpeg version, and imageio-ffmpeg bundled binary version. Supplement package scans for downloaded/bundled binaries.
6. Generate machine-readable SBOMs in a supported standard format, such as CycloneDX, tied to each build. Document exclusions.

Deliverable: raw scan outputs, SBOMs, build manifest, and baseline summary.

Exit check: each in-scope target has evidence or an explicit coverage gap. There is no assumed zero for an unscanned target.

Problem addressed: stale inventories and hidden dependencies in deployed artifacts.

## Step 4 â€” Triage current findings and choose fixes

Actions:

1. Match Excel entries against fresh results and vendor affected/fixed ranges. Capture evidence for fixed, not affected, still open, and pending-validation outcomes.
2. Prioritize known exploitation, external exposure, untrusted document/media processing, and impact alongside severity. Confirm actual code paths rather than deriving exploitability from CVSS alone.
3. Re-check historical libxml2 and PostgreSQL/gosu findings using current advisories. Do not inherit earlier exclusions or dismissals without evidence.
4. Select supported, branch-compatible package/image updates. Group changes that resolve multiple findings. Keep licence/configuration findings separate from vulnerability fixes.
5. For unfixed issues, document mitigations, residual risk, owner, and review date. Keep raw findings visible; any exception must be explicit and time-limited.

Deliverable: ordered, evidence-backed remediation backlog, with a small first batch.

Exit check: each confirmed critical/high finding has a proposed fix or a documented mitigation/decision. Unknown applicability has an investigation action.

Problem addressed: prioritizing by noisy counts and making incompatible version changes.

## Step 5 â€” Implement focused remediation batches

Suggested sequence, adjusted by current scan evidence:

1. Frontend runtime images/packages: update only if still affected, build both apps, validate nginx configuration and proxy traffic.
2. Backend image/packages: address confirmed document/media and OS findings, including actual browser and FFmpeg binaries. Keep required LibreOffice/media functionality.
3. Application dependencies: regenerate the Python hash-checked lockfile consistently and review Dart resolution diffs; avoid unrelated major upgrades.
4. Configuration and parsing: inspect both built frontend environment assets without exposing values. Their Dockerfiles currently write API_BASE_URL; confirm the shipped contents contain only public configuration. If a credential was exposed, remove it and prepare rotation at the affected service. Verify parser limits, entity handling, and browser isolation against actual code.
5. Licence/inventory gaps: verify PyMuPDF entitlement with the maintainer and relevant licence evidence. If replacing it, preserve text/image extraction behavior. Generate third-party notices and capture missing supplier/licence information. Installation presence alone does not establish commercial entitlement.

For each batch: describe the change and affected flows, make a reviewable patch, run relevant checks, rebuild/rescan the target, and record the result before moving to the next batch.

Deliverable: focused patches with test and scan evidence.

Exit check: the intended risks are addressed without unexplained dependency changes or functionality regressions.

Problem addressed: vulnerable runtime components, public configuration leaks, and untracked licence questions.

## Step 6 â€” Verify the complete LMS and reconcile evidence

Actions:

1. Run existing backend tests and relevant Flutter tests/analysis. Reproduce the historical image-slide test failure and classify any remaining failure with evidence; do not report the complete suite as passing if it fails.
2. Exercise trainer/employee login, access boundaries, course authoring, assignment, quiz grading, progress, uploads, PDF/Office processing, slide/image extraction, narration/video generation, playback, WebSockets, and persistence.
3. Use mocks for normal provider tests. Schedule explicit end-to-end provider checks separately where access is available; label unavailable tests unverified.
4. Check production-like settings without sending email or syncing live directories. Verify bundled fonts offline if the deployment requires offline operation.
5. Rescan the final builds. Compare before/after with equivalent targets, scanner settings, and preferably the same database snapshot; distinguish new database advisories from changes introduced by our patches.
6. Produce a closure summary linked to final image identifiers. Retain the original workbook and, if requested, create an updated copy reconciling stale vulnerability and patch-status fields.

Deliverable: test summary, final SBOM/scan evidence, and reconciled findings tracker.

Exit check: no unresolved exploitable critical/high issue is released without a documented maintainer risk decision; no unexplained regression remains; every coverage gap is visible.

Problem addressed: fixes that break the product and unsupported claims that vulnerabilities are resolved.

## Step 7 â€” Prepare and verify deployment

Actions:

1. Prepare a release bundle/manifest for the tested image IDs or digests. For an offline server, include exported images, checksums, and transfer/import instructions.
2. Confirm database/storage backup and recovery procedures, previous image identifiers, configuration differences, and rollback triggers.
3. Perform an authorized deployment to the target environment and check service health and representative trainer/employee workflows. Verify running image identifiers match tested artifacts.
4. Close production findings only after this verification. If server access is unavailable, report local remediation complete and deployment pending.

Deliverable: release/rollback runbook and deployment evidence, when access permits.

Exit check: tested artifacts are running and validated, or deployment is explicitly pending. No production changes are authorized by this planning request alone.

Problem addressed: fixes existing only in source while vulnerable images continue running.

## Step 8 â€” Make the process repeatable for one maintainer

Actions:

1. Create a local PowerShell entry point for inventory, scan, and summary generation. Implement it using the tool versions proven in earlier steps, with clear failures and documented prerequisites.
2. Scan every release; refresh advisory results regularly and after significant dependency changes. Do not create scheduled automations unless requested.
3. Keep image-refresh decisions separate from advisory database refreshes. Rebuild, test, and record new artifacts when bases or downloaded packages change.
4. Enforce a release rule for actionable findings, with expiring, evidence-backed exceptions. Integrate into CI only if a CI environment is available later; the local workflow must stand on its own.

Deliverable: repeatable local workflow and concise maintenance instructions.

Exit check: the maintainer can reproduce a build-linked SBOM and risk report without manually copying spreadsheet rows.

Problem addressed: this becoming a one-time cleanup that drifts out of date.

## Progress checklist

- [ ] Step 1: scope and isolated environment ready
- [ ] Step 2: normalized tracker and report validation complete
- [ ] Step 3: fresh baseline and coverage map captured
- [ ] Step 4: current findings triaged and fixes selected
- [ ] Step 5: focused remediation batches implemented
- [ ] Step 6: tests, final scans, and reconciliation complete
- [ ] Step 7: release prepared and deployment verified, or pending clearly recorded
- [ ] Step 8: repeatable maintenance workflow available

## References and limitations

- Local evidence: the supplied workbook, Dockerfiles, Compose definition, dependency locks, source uses, and `docs/security/vapt-2026-09-25.md`.
- [Trivy vulnerability documentation](https://trivy.dev/docs/latest/scanner/vulnerability/): distribution advisories and backports must be considered; some binary/package sources have detection limitations.
- [CISA Known Exploited Vulnerabilities catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog): consult during prioritization; no LMS advisory's KEV status has been established by this plan.
- SBOM/dependency scanning does not certify application security. Access-control, business-logic, and runtime configuration checks remain separate verification work.
- This plan does not establish legal compliance or decide licence entitlement. Evidence unavailable locally may require the maintainer to obtain purchase/licence records.

Gosu assessment completed: official binary analysis reported no affected vulnerable symbols, and all 46 Trivy gosu advisories mapped to Go database entries without symbol matches. Raw findings are retained; no suppression or replacement binary was introduced. CycloneDX inventories were exported for the verified backend and PostgreSQL candidates (500 and 148 detected components).

Next execution task: build/scan isolated trainer and employee frontend candidates, inspect Dart dependency coverage, and validate serving/rendering behavior. Do not attach live database storage. Existing-data backup/restore rehearsal, remaining coverage/triage, full-stack Hub/UI testing, and final release-linked SBOMs remain release prerequisites. The checklist represents complete phase exit checks; partial component validation does not complete those phases.
