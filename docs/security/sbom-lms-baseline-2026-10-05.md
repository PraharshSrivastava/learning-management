# LMS runtime baseline — 5 October 2026

Scans were run on big-coding-cpu using Trivy 0.75.0, pinned as `aquasec/trivy@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa`.

The VM checkout is `/home/karphi/intelligence_layer`, `main` at `ee45adf`. SSH connects as `phillipcapitalind`; access to the checkout and scan evidence uses `sudo -u karphi`. Untracked environment backups were preserved. No application containers were restarted or recreated.

## Scope and counts

| Target | Critical | High | Medium | Low | Unrated | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Backend image | 1 | 239 | 339 | 279 | 21 | 879 |
| PostgreSQL image | 14 | 141 | 223 | 161 | 7 | 546 |
| Running trainer frontend OS inventory | 0 | 4 | 15 | 2 | 1 | 22 |
| Running employee frontend OS inventory | 0 | 4 | 15 | 2 | 1 | 22 |

Counts are package/advisory occurrences, not distinct exploitable application vulnerabilities. A shared source library can generate repeated occurrences across binary packages. No assertion of exposure or complete application security follows from these totals.

- Backend image: `sha256:6093e61d548ac903f661add8a58897ca959438bd1a1cff1b15d02e4ea429fd64`, report `/home/karphi/lms-security/evidence/backend-baseline.json`.
- PostgreSQL image: `sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b`, report `/home/karphi/lms-security/evidence/postgres-baseline.json`.
- Running trainer image identifier: `sha256:a09ac1f56d61a0f3ff0fdc78bbac4960e6c8bfe98a794c5b391205119398589a`; original image unavailable in the local image store.
- Running employee image identifier: `sha256:83e4b8026f5944bc8993766018c6f77471a78aa6d6d134def1b66898b91fb3ec`; original image unavailable in the local image store.
- Frontend reports and copied package metadata: `/home/karphi/lms-security/evidence/frontend-os-qPiCHj/`. Copies contain `/etc/os-release` and `/lib/apk/db/installed`; scanning used `rootfs --pkg-types os --scanners vuln`. This is OS inventory coverage only, not a full image, Dart dependency, secret, or configuration scan. The scan detected 68 packages per frontend.
- A summary script initially failed after both frontend scans had succeeded. A separate read of all four JSON reports then verified the counts above.

## Findings selected for further work

- Backend urllib3 2.7.0: two high and one medium advisory list 2.8.0 as patched. A focused local requirements change and hash-lock regeneration are prepared; other package resolutions are unchanged.
- Backend Debian PCRE2 and OpenSSL: the reports list supported distribution fixes. A local Dockerfile change requests upgrades for the installed PCRE2/OpenSSL packages during build. The new image must be built and rescanned before claiming remediation.
- Backend pip 25.0.1: six advisory occurrences have listed fixes. The second candidate uses a separate hash-locked pip 26.2.1 bootstrap before application dependency installation; see validation below.
- Each frontend's four high occurrences are two OpenSSL advisories across `libcrypto3` and `libssl3`, installed `3.3.7-r1`, fixed version listed `3.3.7-r2`. Newer available image tags must not be substituted for evidence about the currently running containers.
- PostgreSQL critical occurrences: three Perl advisories repeated across four packages (12 occurrences), libxml2 (one), and Go standard library in `usr/local/bin/gosu` (one). Assess executable behavior and distribution fixes before deployment.
- libxml2 CVE-2026-6653 remains listed without a Trixie fix. Debian's tracker marks the supplied version vulnerable and notes a minor issue/no DSA. Retain it pending application-exposure and mitigation assessment; do not silently suppress it.

## Local patch validation

Branch: `codex/lms-sbom-remediation`, based on local commit `16adda0` (the commit merged into VM `ee45adf`). Application-code equality and final release identity must be checked before candidate deployment.

With urllib3 2.8.0 installed in the local project virtual environment, 22 existing tests passed across TTS request configuration, thumbnail fallback, directory sync, and Langfuse tracing. The first attempt had sandbox temporary-directory failures; rerunning with the required access passed. These tests use controlled fixtures and do not prove real provider/proxy compatibility. Container checks below validate selected dependency functions and installed OS versions; runtime deployment remains pending.

## First backend candidate — verified

The local source bundle was built separately on big-coding as `lms-sbom-backend:candidate-20261005-01`. All 173 transferred source files matched the local SHA-256 manifest. Image identifier reported by Docker: `sha256:8966f58ca1a23a6f95c8ceff7d2e60170359df0ecc5ec0742f60a4ffdd6c1f28`. This is an uncommitted local patch on top of commit `16adda0`, not a published release.

| Severity | Baseline | Candidate |
| --- | ---: | ---: |
| Critical | 1 | 1 |
| High | 239 | 230 |
| Medium | 339 | 311 |
| Low | 279 | 273 |
| Unrated | 21 | 20 |
| Total | 879 | 835 |

Comparison by package ecosystem, package name, and advisory ID found 44 removed occurrences and zero new matches. All three urllib3 advisories, the targeted PCRE2 high advisory, and the six high OpenSSL binary-package occurrences disappeared. Other reductions accompanied refreshed build-time distribution packages; they are not all attributable to the explicit requirements change.

The same Trivy 0.75.0 scanner digest and cached database were used, with candidate DB updates disabled. Saved database metadata: updated `2026-10-05T07:14:49.216148418Z`, downloaded `2026-10-05T08:06:14.997862845Z`.

Installed versions verified inside the candidate:

- urllib3 2.8.0; requests 2.34.2; `pip check` reported no broken requirements.
- libpcre2-8-0 `10.46-1~deb13u3`.
- libssl3t64, openssl, and openssl-provider-legacy `3.5.7-1~deb13u3`.
- Chromium 149.0.7827.55.
- System FFmpeg 7.1.5-0+deb13u1 and bundled imageio-ffmpeg FFmpeg 7.0.2-static. Binary identification is not a dedicated vulnerability assessment of those binaries.

Temporary candidate containers had no external network, published ports, production data mounts, or LMS environment credentials. Tests passed for a chunked/gzip HTTP response, HTTPS acceptance of a trusted local certificate and rejection of an untrusted certificate, generated PDF text extraction, Chromium screenshot rendering, and audio/video encoding with each FFmpeg binary. Real HTTPS proxies/providers, full API/database flows, Hub login, and UI workflows remain unverified.

Build/scan/test evidence: `/home/karphi/lms-security/evidence/backend-candidate-20261005-01/` on big-coding. An initial shell wrapper had a trailing exit/line-ending error after Docker finished the build, and a database-metadata copy initially used the wrong path. Separate image inspection, successful smoke-check execution, JSON report comparison, and corrected metadata capture verified the results above; no build success claim relies on the wrapper exit status.

The original backend was verified still running and healthy on `sha256:6093e61d548ac903f661add8a58897ca959438bd1a1cff1b15d02e4ea429fd64`. No runtime deployment or on-prem UAT change occurred.

Subsequent bootstrap candidate results follow. Browser/media/Dart coverage, configuration review, and database/frontend candidates remain pending. The libxml2 critical finding and other remaining risks require explicit triage. Only after candidate validation should we move to an isolated full-stack Hub/UI test and release decision.

## Pip bootstrap candidate — intermediate result

Candidate `lms-sbom-backend:candidate-20261005-02` installed pip 26.2.1 using the wheel SHA-256 pinned in `backend/requirements-bootstrap.lock`. Application installation remained hash-checked. All 174 transferred files matched the source manifest. Docker image ID: `sha256:54e816c502e89fa51a0bed73cf0fae09495ef607772fa594f834a634b0bea0c3`.

The same offline smoke checks passed, and pip reported no broken requirements. With the unchanged scanner and advisory DB, all six pip advisories disappeared, but six findings appeared in pip's bundled dependency inventory: msgpack 1.1.2 (one high), setuptools 70.3.0 (one high and one medium), and urllib3 2.7.0 (two high and one medium). Installed application urllib3 remained 2.8.0. Imports confirmed pip's bundled urllib3 and msgpack under `site-packages/pip/_vendor/`; Trivy identified the three bundled versions through SBOM analysis in the pip installation layer.

Counts were critical 1, high 234, medium 308, low 272, unrated 20, total 835. This candidate does not establish an overall vulnerability reduction relative to candidate 01. Evidence: `/home/karphi/lms-security/evidence/backend-candidate-20261005-02/`.

Source inspection found no runtime pip invocation in backend application/scripts. The next candidate validates dependencies during the build and uninstalls build-only pip afterwards, including its bundled libraries. This changes runtime administration: dependency changes require rebuilding the image. Full-stack validation remains required.

## Backend candidate with runtime tooling removed — verified

Candidate `lms-sbom-backend:candidate-20261005-03`, Docker image ID `sha256:23f6870c64d8d666dd81e668676b925d54aad4c77e9bb5788f68b8d7f26606e2`, passed the build's `pip check` before uninstalling pip. Runtime checks confirmed pip was absent, application urllib3 remained 2.8.0, and the HTTP/HTTPS, PDF, Chromium rendering, and both FFmpeg encoding smoke checks passed. All 174 files in the final VM build manifest matched the current local working source.

| Severity | Original baseline | Candidate 01 | Final candidate 03 |
| --- | ---: | ---: | ---: |
| Critical | 1 | 1 | 1 |
| High | 239 | 230 | 230 |
| Medium | 339 | 311 | 306 |
| Low | 279 | 273 | 272 |
| Unrated | 21 | 20 | 20 |
| Total | 879 | 835 | 829 |

With the same scanner digest and cached advisory database, comparison by ecosystem/package/advisory found six removed pip occurrences and zero added matches relative to candidate 01. All six bundled-library findings introduced by candidate 02 were absent. Relative to the original baseline, 50 occurrences were removed with zero added matches. Counts describe scanner findings, not a claim of complete security or exploitability. The libxml2 critical finding remains.

Evidence: `/home/karphi/lms-security/evidence/backend-candidate-20261005-03/`, including build/scan/smoke logs, JSON report, comparison, source hashes, scanner DB metadata, and image ID. The original backend remained running and healthy on its original image. No deployment, restart, database change, or on-prem UAT change occurred.

The subsequent PostgreSQL candidate results follow. Frontend candidates, browser/media/Dart coverage, configuration triage, full-stack Hub/UI checks, and release artifact/SBOM generation remain pending.

## Pinned PostgreSQL candidate — verified with synthetic data

The existing Compose reference `postgres:16.15-trixie@sha256:1a6ab3f5345eb6dbe04a1349529caabdb0ab09293a09590fad07b2246bfa4b54` was pulled and scanned separately. Docker reported the same SHA-256 as its image identifier. Runtime version: PostgreSQL 16.15 (Debian `16.15-1.pgdg13+2`), Debian 13.7. The running LMS database remains PostgreSQL 16.14 on its original image; this candidate was not deployed.

| Severity | Running-image baseline | Pinned candidate |
| --- | ---: | ---: |
| Critical | 14 | 2 |
| High | 141 | 89 |
| Medium | 223 | 151 |
| Low | 161 | 133 |
| Unrated | 7 | 7 |
| Total | 546 | 382 |

The scan used the same Trivy digest and cached advisory database as the baseline, with DB updates disabled. Comparison by ecosystem/package/advisory found 164 removed occurrences and zero added matches. The 12 critical Perl occurrences disappeared with installed `libperl5.40` version `5.40.1-6+deb13u1`.

Remaining selected findings:

- Critical libxml2 CVE-2026-6653, installed `2.12.7+dfsg+really2.9.14-2.1+deb13u3`, with no fix listed by the scanner.
- Critical Go standard library CVE-2025-68121 and 21 high Go advisories in `usr/local/bin/gosu`. Runtime identification is gosu 1.19 built with Go 1.24.6. Successful `gosu postgres id` confirmed privilege switching to UID/GID 999. The [upstream gosu documentation](https://github.com/tianon/gosu) describes switching identity then executing the target process; this behavior alone does not establish advisory reachability or justify suppressing the findings. Keep these findings pending focused assessment or a verified replacement build.
- Seven high OS occurrences have listed fixes: one PCRE2 advisory and two OpenSSL advisories across three binary packages. PCRE2 is `10.46-1~deb13u2`, fixed version listed `10.46-1~deb13u3`; OpenSSL packages are `3.5.7-1~deb13u2`, fixed version listed `3.5.7-1~deb13u3`. An isolated derivative image with supported distribution updates is the next focused batch.

An ephemeral test database used a uniquely named Docker volume on an internal network, no published ports, and a generated disposable password. The verified backend candidate 03 connected to this database using the actual LMS repository code. Email scheduling/delivery and directory sync were disabled, with no production environment files, credentials, or data mounts.

Passed checks:

- Fresh database initialization and readiness; entrypoint privilege switching.
- LMS `init_db()` twice, expected startup tables, pooled reads/writes, advisory transaction lock, and transaction rollback with a synthetic trainer record.
- Custom-format `pg_dump` backup and `pg_restore --exit-on-error` into a separate synthetic database, followed by record verification. These are the supported [PostgreSQL dump](https://www.postgresql.org/docs/16/app-pgdump.html) and [restore](https://www.postgresql.org/docs/16/app-pgrestore.html) tools.
- Container restart and verification that the synthetic record persisted.

The first test assertion incorrectly expected every entry in the schema cleanup list to exist after initialization. `course_generation_state` is a legacy cleanup entry and is not created by `init_db()`. Correcting only the smoke test resolved the assertion; no application schema change was made. Both attempts' evidence is retained.

The test container, network, and volume were removed, and absence was checked afterwards. The original database remained running and healthy on `sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b`. No live database backup, restore, restart, or UAT change occurred. Synthetic checks do not validate all existing-data migrations, Hub/UI workflows, or rollback against the deployed database.

Evidence directory: `/home/karphi/lms-security/evidence/postgres-candidate-20261005-01/`, including candidate scan JSON, comparison, DB metadata, image identifier, schema smoke script, successful smoke log, first-attempt log, and PostgreSQL log. A local copy of the comparison is under ignored `tmp/postgres-candidate/`.

The derivative PostgreSQL update results follow. Existing-data backup/restore rehearsal remains a prerequisite for database deployment.

## PostgreSQL distribution update candidate — verified

Added `docker/postgres/Dockerfile`, based on the existing pinned PostgreSQL 16.15 image. It updates only the installed PCRE2/OpenSSL packages through supported Debian repositories, then removes the downloaded apt package lists. Base image pinning does not pin repository contents: record the final image ID and package versions when building a release. Compose still references the upstream image; this patch has not changed deployment behavior.

Candidate tag: `lms-sbom-postgres:candidate-20261005-02`. Docker image ID: `sha256:3fecfb9a134dd7d8fce6510a05822ae3706c49ae70ff9d92bce5c3113be17da1`. The transferred Dockerfile hash matched the local source (`d702f47cccbe4f1ed21354eee398e88e72bc301d7b98e83377db8f0d4dec975d`). Image configuration checks confirmed that the upstream entrypoint, command, user, environment, working directory, volumes, exposed ports, and stop signal were retained.

Verified installed versions:

- PostgreSQL 16.15 (`16.15-1.pgdg13+2`), unchanged from the pinned candidate.
- PCRE2 `10.46-1~deb13u3`.
- libssl3t64, openssl, and openssl-provider-legacy `3.5.7-1~deb13u3`.
- gosu 1.19 built with Go 1.24.6, unchanged; privilege switching to PostgreSQL UID/GID 999 passed.

| Severity | Running-image baseline | Pinned candidate 01 | Updated candidate 02 |
| --- | ---: | ---: | ---: |
| Critical | 14 | 2 | 2 |
| High | 141 | 89 | 82 |
| Medium | 223 | 151 | 124 |
| Low | 161 | 133 | 127 |
| Unrated | 7 | 7 | 7 |
| Total | 546 | 382 | 342 |

The pinned scanner and identical cached database found 40 removed occurrences and zero added advisory matches relative to candidate 01. All seven selected high PCRE2/OpenSSL occurrences disappeared; other removed occurrences were medium and low findings in those OpenSSL binary packages. Relative to the running-image baseline, 204 occurrences were removed with zero added matches. No remaining high Debian occurrence in this report listed a fixed version. This describes scanner evidence at the saved DB timestamp, not proof that remaining findings are harmless.

Repeated synthetic checks passed: fresh initialization/readiness, LMS schema initialization twice, expected tables, pooled reads/writes, advisory locking, transaction rollback, custom-format dump/restore with record verification, and container restart with persisted record verification. The tests used the verified backend candidate 03, an internal Docker network, no published ports, and a unique disposable data volume. No production credentials or data were supplied. The test container, network, and volume were removed and their absence checked afterwards.

The original LMS PostgreSQL container remained running and healthy on its original `sha256:95206741a5b214807675e14165369d05b93a9cf692223b616d07cca227e74b0b` image. No live restart, deployment, storage change, or UAT change occurred.

Evidence: `/home/karphi/lms-security/evidence/postgres-candidate-20261005-02/`, including Dockerfile, source hashes, build log, image identifier, image-configuration comparison, scan log/JSON, advisory DB metadata, scan comparison, schema/test scripts, and smoke/PostgreSQL logs. A local scan comparison is retained under ignored `tmp/postgres-candidate/`.

The gosu assessment and candidate SBOM exports follow. Retain libxml2 as unresolved pending supported fixes/exposure assessment. Frontend candidates, browser/media/Dart coverage, full-stack Hub/UI testing, final release-linked SBOMs, and existing-data backup/restore rehearsal remain pending.

## Exact gosu binary assessment — completed

Extracted `/usr/local/bin/gosu` from PostgreSQL candidate 02 without starting another database. SHA-256: `52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0`. Build metadata confirms gosu v1.19.0, Go 1.24.6, linux/amd64, CGO disabled, github.com/moby/sys/user v0.1.0, and golang.org/x/sys v0.1.0.

Analysis used official govulncheck v1.1.4 in binary/symbol mode inside an isolated Go 1.26.6 analysis container, pinned as `golang@sha256:116d58cbd88c1297624acc6e967a060012422bacf9930927e23fb719189c6f36`. Installing a newer compiler for analysis did not change the extracted binary or its recorded Go version. The tool queried `https://vuln.go.dev`; saved metadata reports database last modified `2026-10-01T20:24:15Z`. This is a different database from Trivy's cached DB and is supporting triage evidence, not a replacement comparison scan.

Results:

- No affected vulnerable symbols were reported. Text-mode exit code was zero.
- The tool reported three package-level and 42 module-level advisories without symbol matches.
- All 46 Trivy advisory occurrences for gosu mapped by CVE aliases to Go database entries; none had a symbol-level match. This includes all 22 high/critical occurrences.
- Critical CVE-2025-68121 mapped to GO-2026-4337 (TLS session resumption); no affected symbol was reported in this binary.

The [official tool documentation](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck) explains that binary mode inspects symbols and cannot produce source call graphs. A clean symbol result supports a lower deployment priority for these specific advisories; it is not proof of complete safety. Review is bound to the exact binary hash and should be repeated when the image/binary or advisory information changes. No `.trivyignore` rule or scanner-count reduction was applied. The raw PostgreSQL total remains 342, with two critical findings.

The upstream [latest release](https://github.com/tianon/gosu/releases/latest) resolved to 1.19 during verification. No newer upstream release binary was available through that release page. A controlled rebuild of the same source with a patched, pinned Go toolchain is a possible hardening option, but would become a maintained custom artifact requiring provenance, binary analysis, privilege-switching tests, and database retesting. Given the current no-symbol-match evidence, this assessment retains the upstream binary and prioritizes the untested frontend components next. No vulnerability exemption or release approval is implied.

Evidence: `/home/karphi/lms-security/evidence/gosu-assessment-20261005/`, containing the extracted binary, build/tool metadata, pinned analysis-image identity, full JSON/text output, and `assessment.json` mapping all 46 Trivy advisories. A local assessment copy is under ignored `tmp/security-sboms/`.

## Candidate SBOM artifacts — exported

Converted the saved verified candidate scan reports to CycloneDX 1.7 inventories using the same pinned Trivy converter with external networking disabled. These exports did not rescan the images or refresh vulnerability databases. Separate original JSON scan reports retain the vulnerability findings; the CycloneDX files are inventory exports.

- Backend candidate 03: 500 detected components, `/home/karphi/lms-security/evidence/backend-candidate-20261005-03/candidate.cdx.json`; local `tmp/security-sboms/backend-candidate.cdx.json`. SHA-256: `1f7b495bb0538a399b12fa10eae0cfca493135ff1b01c3b3b4abed63cf101c93`.
- PostgreSQL candidate 02: 148 detected components, `/home/karphi/lms-security/evidence/postgres-candidate-20261005-02/candidate.cdx.json`; local `tmp/security-sboms/postgres-candidate.cdx.json`. SHA-256: `287e742a841adaea590bc694d9a793b3854f88d9da6e4572d2acbd027bf4ca7e`.

Both files parsed as JSON, declared CycloneDX 1.7, contained unique component references, and included metadata identifying the tested candidate image hashes. Full CycloneDX schema conformance was not independently validated. The backend converter warned that several detected licence strings could not be normalized as SPDX expressions; retain original scan metadata for licence review. These inventories reflect scanner detection coverage, not guaranteed complete browser/media/Dart or whole-LMS inventories. Final release images still require their own linked SBOMs and checks.

Next execution batch: build and scan isolated trainer/employee frontend candidates, inspect Dart dependency coverage, and validate their serving/rendering behavior before full-stack Hub/UI testing.
