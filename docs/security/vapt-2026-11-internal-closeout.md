# Internal VAPT close-out — November 2026

Source: `learning-management-vapt-20261117-135042` (scan of 17 Nov 2026).
Branch: `fix/vapt-internal-2026-11`, cut from `main` at `171e2a7`.
Plan: [vapt-2026-11-implementation-plan.md](vapt-2026-11-implementation-plan.md), Track A.

Every finding has one outcome: **Fixed**, **Already fixed**, **False positive**, **Accepted**, **Deferred to Track B** or **Out of scope**.

## Outcome by scanner

| Scanner | Reported | Outcome |
|---|---:|---|
| Semgrep | 37 | 11 fixed, 4 mitigated and annotated, 12 accepted by design, 1 already fixed, 9 false positive |
| Bandit | 156 | HIGH 1 fixed; MEDIUM 29 reviewed (0 real); LOW 126 covered by `.bandit` with reasons |
| pip-audit | 45 | 43 already fixed (stale venv); `opentelemetry-api` fixed |
| Trivy fs | 2 | Fixed (`seroval`) |
| Trivy image | 897 | Base-image scan. Built images rescanned on big-coding on 23 Nov 2026 (with the vendor branch on top): backend 0 Critical, 0 High, no finding with a published fix; front ends 0 findings. Postgres (543) → out of scope |
| Trivy config / hadolint | 24 / 75 | hadolint now reports 0 on both Dockerfiles: 31 fixed, 4 rules accepted in `.hadolint.yaml` with reasons |
| gitleaks | 0 | Clean |
| Secret patterns / sensitive files | 14 / 2 | False positive |

## Fixed

| Finding | Change |
|---|---|
| nginx h2c smuggling on asset and video locations (8 of 12 hits) | `Upgrade`/`Connection` forwarding removed from the four non-API locations in `apps/trainer/nginx.conf` and `apps/employee/nginx.conf`. Nothing there uses WebSockets. |
| `seroval` 1.6.8 — CVE-2026-116582, CVE-2026-116583 | Workspace override to `^1.6.11`; lock file now resolves 1.7.7. |
| pnpm `trustPolicy`, `blockExoticSubdeps` missing | Both set in `pnpm-workspace.yaml`. `semver@6.3.1` is excluded from the trust check with a reason (legacy line published before provenance existed). |
| `opentelemetry-api` 1.44.0 — CVE-2026-114603, CVE-2026-126360 | Pinned to 1.45.2 in `backend/requirements.txt`; lock recompiled for the OpenTelemetry family only (1.45.2 / 0.66b2). The scan listed one CVE; pip-audit on the real lock file showed two. |
| MD5, Bandit HIGH B324 | `usedforsecurity=False` in `scripts/security/backend_bundle_inventory.py` (it compares dpkg checksums). |
| hadolint DL4006 (24), DL3042 (2), DL3025 (1+1), SC2046 (2), DL3066 (1) | `SHELL ["/bin/bash", "-o", "pipefail", "-c"]` in every backend build stage; `--no-cache-dir` on the offline pip installs; JSON-form `HEALTHCHECK CMD` in both Dockerfiles; the two compiler-flag expansions carry a reasoned inline ignore; `USER 0` in `deploy/web.Dockerfile`. |
| Base images behind their tags | Digests refreshed for `ubuntu:26.04`, `python:3.12.14-slim-trixie` and `nginx-unprivileged:1.31.6-alpine3.24` (Node was already current). |
| Front-end image CVEs (libx11, libxpm) | Rebuilt images carry libx11 1.8.14-r0 and libxpm 3.5.20-r0; Trivy reports 0 vulnerabilities on both. |

## Already fixed before this round

| Finding | Evidence |
|---|---|
| Pillow 12.3.0, 43 advisories; certifi | `main` has Pillow 13.0.0 and certifi 2026.10.18 (PR #53). The scan read an old `backend/.venv`. pip-audit on the lock file reports neither. |
| npm minimum release age | `minimumReleaseAge: 20160` was already in `pnpm-workspace.yaml` and `.npmrc`. |

## Mitigated and annotated

| Finding | Reason |
|---|---|
| nginx h2c smuggling on the two `/api/` locations per file (4 hits) | WebSockets are needed here. `Upgrade` is forwarded only when the client sent exactly `websocket` (`map $http_upgrade $websocket_upgrade`), so an `h2c` upgrade is never passed on. Annotated in place. |
| SQL built with f-strings, 23 sites in `backend/app` (Bandit B608) | Each site read once. Only fixed table/column names, constant clauses or `?` placeholder lists are interpolated; every value is a bound parameter. Annotated with `# nosec B608` and the reason. Bandit now reports 0 Medium and 0 High for `backend/app`, `scripts`, `backend/security`. |

## Accepted by design

| Finding | Reason |
|---|---|
| nginx forwards the client `Host` header (12 hits) | Intentional. The Hub edge proxy owns the public host name and the pass-through is pinned by `backend/tests/test_nginx_public_mount.py`. The backend takes no access decision from `Host`. The deployment host names are not known to the image, so an allow-list cannot be built in. Review 2027-02-20. |
| Dockerfile `RUN cd`, unpinned apt, intermediate-stage `USER`, `mount`/`su` in a build stage (DL3003, DL3008, DL3002, DL3001) | Recorded with reasons in `.hadolint.yaml`. |

## False positive

| Finding | Reason |
|---|---|
| CSV formula injection, `api/email_status.py:116` | Cells that start with `=`, `+`, `-` or `@` are already prefixed with `'`. |
| "Use defusedxml", `pdf_builder.py:8`, `workflow_export.py:6` | Only `xml.sax.saxutils.escape` is imported. It escapes text and parses nothing. |
| Logger credential leak, `core/providers.py:190` | The line logs a course id, a stage name and token counts. |
| `dangerouslySetInnerHTML`, `Icon.tsx:31` | The body comes from the icon set bundled with the app, not from user input. |
| Subprocess taint, `backend/security/record_source_wheel.py:66` | Build-time script; tool names come from the Dockerfile. |
| XML parser and dynamic URL in `scripts/security/*` | Developer scripts. The parser reads fixed byte strings to regression-test Expat; the URLs are two hard-coded HTTPS GitHub addresses. Annotated in place. |
| `0o700` on a temporary GnuPG directory | Owner-only is the correct mode. |
| Secret patterns (14) | Variable names such as `token =` and test markers. |
| Sensitive files (2) | Both are `.env.example`, a template. |
| Bandit MEDIUM in `backend/tests` (4) | Test fixtures; `backend/tests` is excluded in `.bandit`. |

## Still open

| Item | State |
|---|---|
| Backend image: full build and Trivy scan of the built image | **Done** on big-coding, 23 Nov 2026, as part of the vendor branch (`0e350a8`), which contains every change in this branch. Build passed; release gate passed. See `vapt-2026-11-vendor-response.md`. |
| Trivy config DS-0013 (`RUN cd`, 24) | Same pattern as hadolint DL3003, accepted with the reason in `.hadolint.yaml`. |
| Semgrep re-run | Not run: the tool could not be downloaded in WSL (two attempts). The `nosemgrep` annotations are untested until the big-coding rescan. |

## Out of scope

| Finding | Reason |
|---|---|
| Postgres base image, 543 findings (2 Critical, 152 High) | Decision of 20 Nov 2026: no database or Postgres changes in this round. |

## Verification

| Check | Result |
|---|---|
| Bandit, `-ll`, `backend/app` + `scripts` + `backend/security` | 0 Medium, 0 High |
| pip-audit on `backend/requirements.lock` | Before: `opentelemetry-api`, 2 CVEs. After: no known vulnerabilities |
| hadolint, both Dockerfiles | 0 findings |
| Front-end images built; `nginx -t` | Pass (trainer, employee) |
| Trivy on built front-end images | 0 vulnerabilities |
| `test_nginx_public_mount.py` against real nginx | 4 passed |
| Backend pytest (WSL, throwaway Postgres) | Pass |
| Ruff on `backend/app` | 25 warnings, all in files this branch does not touch |
| Front-end build (trainer, employee) | Pass |
| Front-end tests | 569 passed |

