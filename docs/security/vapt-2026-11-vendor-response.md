# Response to the SBOM revalidation (LMS) — November 2026

Responds to *SBOM Revalidation – Internal Applications*, version 2.0, 14 October 2026 (DigitalTrack), LMS rows only.
Branch: `fix/vapt-vendor-2026-11`, stacked on `fix/vapt-internal-2026-11`.

The revalidation assessed the component set of 9 October. Since then the LMS front ends moved from Flutter to React and the backend dependencies were updated, so several findings were already resolved when the report arrived.

Status words: **Fixed** (changed in this branch), **Already fixed** (resolved on `main` before this round), **Evidence** (no defect; the requested statement or file is supplied), **Accepted** (no fix exists; see [accepted risks](vapt-2026-11-accepted-risks.md)), **Pending build** (change made; needs the backend image built on the release server to confirm).

## Findings

| ID | Severity | Finding | Status | Response |
|---|---|---|---|---|
| F-02 | High | AGPL PDF library (PyMuPDF) | **Fixed** | PyMuPDF is removed from the application, tests, build records and tooling. No commercial licence was held. PDF reading now uses pdfplumber (MIT), pdfminer.six (MIT) and pypdfium2 (Apache-2.0 / BSD-3-Clause), which were already in the image. On four real course PDFs the new reader returns the same images as PyMuPDF did (same page, object, position and size; 45 of 45). |
| F-03 | High | `flutter_dotenv` in a web front end | **Already fixed** | The Flutter front ends no longer exist. The React apps take one build-time value, `VITE_API_BASE_URL`, which is a public URL. No `.env` file and no secret is shipped to a browser. |
| F-04 | High | No vulnerability scan with the SBOM | **Fixed** | `scripts/security/release-evidence.sh` writes, for each image, the CycloneDX SBOM and the Trivy vulnerability report side by side, and fails the release when a Critical or High finding has a published fix. Run against both front-end images: gate PASS, 0 vulnerabilities. |
| F-05 | Medium | Image tags float | **Already fixed** | Every `FROM` in `backend/Dockerfile` and `deploy/web.Dockerfile`, and the `postgres` image in `docker-compose.yml`, is pinned by digest. The evidence script copies these three files into the package. |
| F-07 | Medium | Scanner suppressions filter published output | **Evidence** | Trivy runs with no ignore file, so the published vulnerability report is unfiltered. The only scanner settings in the repository are `.bandit` and `.hadolint.yaml`; each entry carries its reason and a review date of 20 February 2027, and both files are copied into the evidence package. |
| F-08 | Medium | Untrusted documents parsed in the backend | **Fixed** / **Evidence** | Controls are described in [document-parsing-controls.md](document-parsing-controls.md). Added in this branch: an upload is refused when its first bytes do not match its extension. XML is parsed only inside python-docx and python-pptx, both with entity resolution off. One gap is recorded there: no memory or CPU cap on the backend container. |
| F-10 | Medium | Headless browser unrecorded | **Fixed** | The image build now records the Chromium build Playwright installed (`/usr/share/lms-security/notices/third-party-inventory.json`), and the evidence script adds it to the SBOM as a component. On the built image: Chromium 153.0.8010.12, Playwright build 1243. The browser is installed at image build (`playwright install chromium`) and is never downloaded at run time. It is started with Playwright's default settings, under which Chromium's own sandbox is off; isolation comes from the container (non-root user, all capabilities dropped, `no-new-privileges`). It opens only local slide files that the LMS itself generated and never navigates to a remote address. |
| F-11 | Medium | LGPL components without notices | **Fixed** | The backend image now contains `/usr/share/lms-security/notices/THIRD-PARTY-NOTICES.txt`, generated at build: every Python package and OS package with its licence, supplier and the path of its licence text. Each front-end image contains `/usr/share/licenses/lms/third-party-licenses.json` for the bundled JavaScript packages. |
| F-12 | Medium | Fonts fetched at run time | **Already fixed** | `google_fonts` left with Flutter. The React apps load fonts bundled in the build (`packages/shared/src/fonts`). |
| F-14 | Low | Licence metadata incomplete | **Evidence** | The remaining gaps named in the report are Go modules in other applications' images. For LMS, the notice inventory above records a licence for every Python package. |
| F-15 | Low | `flutter_lints` behind | **Already fixed** | Not applicable: no Flutter code remains. The React code is checked with ESLint, TypeScript and Prettier. |
| F-16 | Low | Supplier missing from the SBOM | **Fixed** | `scripts/security/finish_sbom.py` adds the supplier to each component from the image's own package metadata. On the front-end images: 70 of 71 components. |
| N-04 | Low | Backend moved from Debian to Ubuntu without a note | **Evidence** | The backend runtime moved to `ubuntu:26.04` (digest-pinned) during the October SBOM remediation; the Python runtime is still copied from the digest-pinned `python:3.12.14-slim-trixie` image. Ubuntu 26.04 is an LTS release; its support end date is to be entered in the platform lifecycle tracker by DevOps. |

## Vulnerabilities (34 rows)

| Image | Component | Rows | Status | Response |
|---|---|---:|---|---|
| Both front ends | libx11 1.8.13-r0 | 8 | **Fixed** | Rebuilt images carry 1.8.14-r0. |
| Both front ends | libxpm 3.5.19-r0 | 2 | **Fixed** | Rebuilt images carry 3.5.20-r0. Trivy reports 0 vulnerabilities on both images. |
| Backend | util-linux 2.41.3 (4 High) | 4 | **1 fixed, 3 accepted** | Rescanned on big-coding (23 November 2026). CVE-2026-78409 no longer appears. CVE-2026-76642, CVE-2026-78408 and CVE-2026-78410 remain, now rated Medium by Ubuntu, with no fixed version published. They are reported both for Ubuntu's `util-linux` 2.41.3 and for the image's own util-linux 2.42.4 build (packages `lms-*`), so the replacement does not clear them. The affected code paths (`mount` helpers, `nsenter --join-cgroup`, bind mounts) need privileges the container does not have: it runs as a non-root user with all capabilities dropped and `no-new-privileges`. |
| Backend | coreutils | 3 | **Fixed** | The rebuilt image carries `gnu-coreutils` 9.7-3ubuntu2.1, the fixed version; the scan reports no coreutils findings. |
| Backend | dash | 2 | **Accepted** | No fixed version is published. |
| Backend | tar | 2 | **Accepted** | No fixed version is published. |
| Backend | Go stdlib 1.26.7 | 13 | **Fixed** | The only Go binary in the image was `/usr/bin/pebble`, Canonical's service manager, which ships in the Ubuntu base image, belongs to no package and is not used by the LMS. It is now deleted in the build. On the first rebuild it carried Go 1.27.3 with one Medium finding; the 13 rows of 1.26.7 were already gone. |

## Found on the rescan and fixed

The first rebuild on big-coding showed nine Medium findings that the October work had introduced: the image replaced one library each in Poppler and GStreamer with its own patched build, and those builds were labelled older than Ubuntu's later security updates (poppler 26.01.0-2ubuntu0.2 and 0.3, gst-plugins-base1.0 1.28.2-1ubuntu0.2 and 0.3). Both of the image's patches were checked and are already included in Ubuntu's current patch series, so the custom builds were removed and Ubuntu's packages are used. A build step now fails if an older or custom version of either package is installed.

## Checks run

| Check | Result |
|---|---|
| Backend test suite | Pass |
| PDF comparison, old against new reader, 4 real PDFs | 45 of 45 images identical; all extracted files open |
| Front-end images build, `nginx -t`, hadolint | Pass, 0 lint findings |
| Backend, trainer and employee images built on big-coding (23 November 2026) | Pass; backend 29 minutes |
| `release-evidence.sh` on all three images | Gate PASS: backend 0 Critical, 0 High; front ends 0 findings |
| PDF reader inside the backend image, no network | Text, layout blocks and image extraction work |
| PyMuPDF in the backend image | Not present |
| Backend rebuilt after the Poppler, GStreamer and pebble fix (`29a561c`) | Gate PASS: 0 Critical, 0 High, 79 Medium, 17 Low, none with a published fix. Poppler 26.01.0-2ubuntu0.3 and gst-plugins-base 1.28.2-1ubuntu0.3 installed; pebble absent; RTSP regression 6 of 6 passed; LibreOffice conversion and PDF reader work |
