# Accepted risks — VAPT round of November 2026

Findings that are not fixed, with the reason. Review date for every row: **20 February 2027**. Approver: to be named by the security owner.

| Item | Source | Why it is not fixed | Exposure and mitigation | Owner |
|---|---|---|---|---|
| dash, 2 Medium (UBUNTU-CVE-2026-102473, -102474) | Vendor | Ubuntu has published no fixed version | Local shell only. The backend exposes no shell; the container runs as a non-root user with all capabilities dropped | LMS team |
| tar, 2 Medium (UBUNTU-CVE-2026-18508, -18477) | Vendor | Ubuntu has published no fixed version | The application does not unpack user-supplied archives with `tar` | LMS team |
| nginx forwards the client `Host` header | Internal | Intentional: the Hub edge proxy owns the public host name, and the image does not know the deployment host names | The backend takes no access decision from `Host`; behaviour is pinned by `test_nginx_public_mount.py` | LMS team |
| Dockerfile `RUN cd` and unpinned apt packages | Internal | Style rules; the base image is digest-pinned and the native inventory is recorded | None needed | LMS team |
| No memory or CPU cap on the backend container | Vendor F-08 | Values must be measured on the UAT server because video generation shares the container | Upload size, conversion time and image size are capped | DevOps |
| PostgreSQL image, 543 base-image findings | Internal | Out of scope for this round by decision of 20 November 2026 | By default the database port is published on the server's loopback address only (`127.0.0.1`) | DevOps |

Still to be classified once the backend image is built on the release server: coreutils (3 rows), Go stdlib 1.26.7 (13 rows), and confirmation of the util-linux replacement (4 rows).
