# VAPT fixes — implementation plan (November 2026)

Two separate tracks, two separate branches and PRs, both cut from `main` (`171e2a7`):

| Track | Source | Branch |
|---|---|---|
| **A — Internal VAPT** | `learning-management-vapt-20261117-135042` (our own scanners, 17 Nov) | `fix/vapt-internal-2026-11` |
| **B — Vendor VAPT** | `SBOM-internal-apps-revalidation.xlsx` (DigitalTrack v2.0, 14 Oct, LMS rows only) | `fix/vapt-vendor-2026-11` |

Order: Track A first (small code changes), then Track B (image rebuild + evidence), then one shared rescan.

## Rules for this work

1. **Every finding gets exactly one outcome:** Fix · Already fixed (send evidence) · False positive (written reason) · Accepted risk (no upstream fix exists; owner + review date).
2. **One attempt per fix.** If a fix does not work on the first clean attempt, or needs more than the stated limit, stop and record it as accepted risk or a follow-up. No retry loops. The October PyMuPDF source rebuild is the example of what not to repeat.
3. **No custom native rebuilds** beyond what `backend/Dockerfile` already does.
4. Nothing is deployed until the rescan in Step 3 is reviewed.
5. **Database / PostgreSQL is out of scope** (decision 20 Nov 2026): no change to the Postgres image, its configuration or the database. Its scanner findings are listed as out of scope, not fixed.
6. **PyMuPDF:** the company holds no Artifex commercial licence (confirmed 20 Nov 2026), so F-02 is a replacement, one attempt.

---

## Track A — Internal VAPT

### A1. Code fixes (real)

| # | Finding | File | Change | Limit |
|---|---|---|---|---|
| A1.1 | nginx h2c smuggling (12 hits) | `apps/trainer/nginx.conf`, `apps/employee/nginx.conf` | Only forward `Upgrade`/`Connection` on the WebSocket locations; everywhere else send `Connection ""` and no `Upgrade`. On WebSocket locations accept only `Upgrade: websocket` via a `map`. | 1 pass |
| A1.2 | nginx `$http_host` trusted (12 hits) | same two files | Replace `proxy_set_header Host $http_host` with a fixed/validated host (`$host` plus a `server_name` allow-list, default server returns 444). Re-run `backend/tests/test_nginx_public_mount.py`. | 1 pass |
| A1.3 | `seroval` 1.6.8, 2 CVEs | `pnpm-lock.yaml` | Bump to ≥1.6.11 (pnpm override if it is transitive). | 1 pass |
| A1.4 | pnpm supply-chain settings | `pnpm-workspace.yaml`, `.npmrc` | Add `trustPolicy: no-downgrade` and `blockExoticSubdeps: true`. `minimumReleaseAge` is already set in the workspace file; mirror it in `.npmrc`. | 1 pass |
| A1.5 | MD5 (Bandit HIGH, B324) | `scripts/security/backend_bundle_inventory.py:101` | Add `usedforsecurity=False` (it is a file fingerprint, not security). | trivial |
| A1.6 | Unsafe XML parser in dev script | `scripts/security/backend_parser_smoke.py` | Switch to `defusedxml.ElementTree` (add `defusedxml` to dev requirements). | trivial |
| A1.7 | `opentelemetry-api` CVE-2026-126360 | `backend/requirements.lock` | Lock has 1.44.0; scan saw 1.45.1 in a stale venv. Bump to ≥1.45.2 if the advisory covers 1.44.0; otherwise mark already-safe. | 1 pass |
| A1.8 | 25 SQL f-strings (Bandit B608) | `backend/app/repositories/*`, `services/assignments.py`, `services/email_notifications.py` | Review each once. If only fixed fragments/placeholders are interpolated → add `# nosec B608` with a one-line reason. If any user value is interpolated → convert to a bound parameter. | 1 review pass, no refactors |
| A1.9 | Dockerfile lint (hadolint 75, Trivy config 24) | `backend/Dockerfile` | Cheap ones only: `SHELL ["/bin/bash","-o","pipefail","-c"]`, `pip --no-cache-dir`, JSON `CMD`. `RUN cd` (DL3003) and unpinned apt (DL3008) are **accepted** — rewriting 500 lines of working build for style is not worth the risk. Record in `.hadolint.yaml`. | 1 pass |

### A2. Already fixed — stale scan input

| Finding | Reason |
|---|---|
| Pillow 12.3.0 (43 advisories), certifi | `main` has Pillow 13.0.0 and certifi 2026.10.18 (PR #53). pip-audit scanned an old `backend/.venv`. Rebuild the venv before the rescan. |

### A3. False positives — record the reason, no code change

| Finding | Reason |
|---|---|
| CSV injection, `api/email_status.py:116` | Cells starting with `= + - @` are already prefixed with `'`. |
| "Use defusedxml", `pdf_builder.py:8`, `workflow_export.py:6` | Only `xml.sax.saxutils.escape` is imported — it escapes text, it parses nothing. |
| Logger credential leak, `core/providers.py:190` | Logs course id, stage and token *counts*; no secret. |
| Secret patterns (14), sensitive files (2) | Variable names / test markers; `.env.example` is a template. Confirm it has placeholders only. |
| `dangerouslySetInnerHTML`, `Icon.tsx:31` | Static bundled SVG strings, no user input. Confirm once. |
| Subprocess taint, `backend/security/record_source_wheel.py:66` | Build-time script, arguments come from the Dockerfile. |
| Bandit LOW ×126 (subprocess, partial path) and test-only MEDIUMs | ffmpeg/LibreOffice calls with list arguments, no shell; tests. Cover with `.bandit` config, each with a reason. |
| `0o700` permissions, dynamic urllib in `scripts/security/*` | Dev-only scripts; 0o700 is owner-only. |

### A4. Base-image CVEs (897)

These came from scanning the three *base* images, not our built images. The backend and front-end images are handled once in **B2** (rebuild + rescan of the real images). The 543 Postgres-image findings are out of scope (Rule 5).

**Track A status:** implemented on `fix/vapt-internal-2026-11`; outcomes per finding are in `vapt-2026-11-internal-closeout.md`. Two items changed from this plan after reading the code: the nginx Host pass-through (A1.2) is intentional and pinned by a test, so it is documented rather than changed; and the Dockerfile lint fixes and base-digest bumps were done here instead of in Track B, leaving only the full backend image build and scan for big-coding.

---

## Track B — Vendor VAPT (DigitalTrack revalidation)

### B1. Close with evidence only (already fixed on `main`)

| ID | Sev | Finding | What we send |
|---|---|---|---|
| F-03 | High | `flutter_dotenv` in front end | Statement: Flutter front ends removed; React builds take one public value (`VITE_API_BASE_URL`); no `.env` shipped to browsers. |
| F-12 | Med | `google_fonts` runtime fetch | Statement + path: fonts are bundled (`packages/shared/src/fonts`), no runtime fetch. |
| F-15 | Low | `flutter_lints` 4.0.0 | Not applicable — Flutter removed; ESLint/Prettier in use. |
| F-05 | Med | Image tags float | Supply `backend/Dockerfile`, `deploy/web.Dockerfile`, `docker-compose.yml` — all digest-pinned. |
| N-04 | Low | Debian → Ubuntu not recorded | Package note explaining the move + Ubuntu 26.04 support end date in the lifecycle tracker. |

### B2. Image CVE fixes (34 vendor rows + internal A4)

| # | Image | Package | Action | Limit / fallback |
|---|---|---|---|---|
| B2.1 | both front ends | libx11 1.8.13, libxpm 3.5.19 (2 High, 8 Med) | Bump the nginx base digest and rebuild; `apk upgrade` is already in the Dockerfile. Verify 1.8.14-r0 / 3.5.20-r0 in the result. | 1 rebuild. If Alpine has not published the fix: remove the X11 packages from the nginx image if nothing needs them, else accepted risk. |
| B2.2 | backend | coreutils (2 Med + USN-8697-1) | Bump the Ubuntu 26.04 digest; `apt-get upgrade` already runs. Check the `coreutils-from-gnu` swap picks up 9.7-3ubuntu2.1. | 1 rebuild |
| B2.3 | backend | util-linux, 4 High, no Ubuntu fix | Find which util-linux binary packages are still stock 2.41.3 after our 2.42.4 replacement and extend the existing `package_util_linux.py` list to cover them. | **1 attempt.** If it does not build cleanly: accepted risk (local-only, needs mount privileges the container does not have). |
| B2.4 | backend | Go stdlib 1.26.7, 13 unrated | Identify the Go binary (one `trivy` query on the image). If it is not needed at runtime, remove it; if needed, update the package. | **30 min.** Otherwise accepted risk with reachability note. |
| B2.5 | backend | dash, tar (4 Med) | No fix exists upstream. | Accepted risk, 90-day review. |

### B3. Evidence and process items

| ID | Sev | Finding | Deliverable |
|---|---|---|---|
| F-04 | High | No scan with the SBOM | Extend `scripts/security/scan-candidates.sh` to write Trivy vulnerability JSON next to each CycloneDX file and exit non-zero on fixable Critical/High. This is the build gate (there is no CI in the repo; the script runs on big-coding before release). |
| F-07 | Med | Suppressions not published | Ship `.bandit`, `.hadolint.yaml` and a `.trivyignore` (each entry with reason + expiry date) in the evidence package. |
| F-08 | Med | Untrusted document parsing | One-page `docs/security/document-parsing-controls.md`: where parsing runs, upload size/type checks, timeouts, lxml with `resolve_entities=False, no_network=True, load_dtd=False`. If any lxml parser call lacks those flags, fix it in this branch. |
| F-10 | Med | Headless browser unrecorded | Record the Chromium version from `playwright install` in the SBOM (via existing `augment_backend_sbom.py`); state that it is baked in at build time, never downloaded at run time, and renders only our own generated HTML. |
| F-11 | Med | LGPL without notices | Generate `THIRD-PARTY-NOTICES.txt` at build (`pip-licenses` for Python, `pnpm licenses` for JS, dpkg copyright list for OS) and copy it into each image. |
| F-14 / F-16 | Low | Licence / supplier metadata | Fill supplier in `augment_backend_sbom.py` where the ecosystem provides it. One pass; gaps that upstream does not publish stay empty and are noted. |

### B4. Decision needed — F-02 PyMuPDF (High, AGPL)

Used in two files only: `document_builder/import_source.py` and `generation/blueprint.py`.

1. No Artifex commercial licence is held (confirmed 20 Nov 2026).
2. **Replace** with `pypdfium2` (BSD/Apache) for rendering and image extraction plus the already-installed `pdfplumber` for text. **Limit: one working session.** Compare output on the existing course PDFs.
3. **If the replacement loses image/text quality:** stop, keep PyMuPDF, and raise a licence purchase request. No second attempt.

**Track B status:** implemented on `fix/vapt-vendor-2026-11`; outcomes per finding are in `vapt-2026-11-vendor-response.md`. PyMuPDF was replaced on the first attempt. The backend image CVE rows (util-linux, coreutils, Go) and the backend evidence package wait for the image build on big-coding.

---

## Step 3 — Shared rescan and hand-off

1. Rebuild backend, trainer, employee images from the merged commit on big-coding. Postgres is not touched.
2. Run the same internal scanner set on a fresh venv and on the **built** images (not the bases).
3. Produce:
   - `docs/security/vapt-2026-11-internal-closeout.md` — Track A table with outcomes.
   - `docs/security/vapt-2026-11-vendor-response.md` — Track B table keyed by vendor ID, plus Dockerfiles, SBOMs, Trivy output, suppression files, notices file.
   - `docs/security/vapt-2026-11-accepted-risks.md` — package, CVE, why it cannot be fixed, mitigation, owner, review date.
4. Functional smoke on big-coding (login via Hub, course create, PDF import, video generation, CSV export, WebSocket progress) — nginx and PDF changes are the ones that can break things.
5. Deploy only after review.

## Checks

- Backend: ruff + pytest in WSL (`~/lms-refactor` venv, throwaway Postgres on :55432).
- Front end: `corepack pnpm` lint, typecheck, test, build.
- nginx: `nginx -t` in the built image + `test_nginx_public_mount.py`.

## Expected hard spots (where Rule 2 will most likely apply)

| Item | Risk | Fallback already decided |
|---|---|---|
| B4 PyMuPDF replacement | Image extraction quality | Licence purchase |
| B2.3 util-linux | Source build of extra packages | Accepted risk |
| B2.4 Go stdlib | Binary may belong to a third-party tool | Accepted risk |
| Postgres | Out of scope by decision | Not touched |
| A1.1/A1.2 nginx | WebSocket or Hub launch breaks | Revert that hunk, keep the rest |
