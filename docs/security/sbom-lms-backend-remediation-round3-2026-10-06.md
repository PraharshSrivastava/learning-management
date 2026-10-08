# LMS backend High remediation — round 3

Historical candidate 16 evidence. Current selection and remaining backlog are in [round four](sbom-lms-backend-remediation-round4-2026-10-07.md).

Date: 6 October 2026. State: isolated candidate tested; not deployed. PostgreSQL security work remains deferred.

The inherited High backlog is reduced from **61 to 14 package-advisory occurrences**. This batch patches affected components behind 36 occurrences, removes a component behind two, and verifies that the specific vulnerable implementation is absent for nine. The nine applicability assessments are not software upgrades. The Critical XML finding was addressed in round 2 and remains addressed.

| Inherited backlog | Before this batch | After this batch |
| --- | ---: | ---: |
| Critical | 0 | 0 |
| High | 61 | 14 |
| Medium | 97 | 97 |
| Low | 195 | 195 |
| Unknown | 20 | 20 |

These retain the original Debian severities and every original row. The original 829-row register now has 503 addressed and 326 open occurrences; the original Critical/High/Medium subset has 426 addressed and 111 open. An advisory affecting nine related packages counts as nine occurrences, not nine unique vulnerabilities. See the [complete inherited register](sbom-lms-backend-inherited-round3-2026-10-06.csv).

## Changes and evidence

Upgraded the affected util-linux libraries and tools to **2.42.4**: libmount, libblkid, libuuid, mount, umount and nsenter. Four named advisories each appeared against nine original packages, accounting for 36 High occurrences. The fixes prevent unsafe mount helper/post-hook handling, subdirectory escape, restricted bind-source redirection and an inherited cgroup descriptor in nsenter. The nsenter follow-up requires 2.42.4; using only 2.42.3 would be incomplete. Primary evidence: [Debian tracker for nsenter](https://security-tracker.debian.org/tracker/CVE-2026-78408), [mount helper](https://security-tracker.debian.org/tracker/CVE-2026-76642), [subdirectory handling](https://security-tracker.debian.org/tracker/CVE-2026-78409), and [bind source](https://security-tracker.debian.org/tracker/CVE-2026-78410). Eight primary advisory pages and both upstream release notes are preserved with the evidence.

This is a partial, operator-maintained replacement. Other Ubuntu util-linux utilities remain at their original versions; no family-wide upgrade is claimed. Four explicitly named LMS packages record source/version `2.42.4+lms1`. Library packages provide the tested older Ubuntu ABI to satisfy existing exact-version dependencies. Their compatibility declaration does not change the real code version. Versioned ELF exports, existing findmnt compatibility, mount-table parsing, UUID round-trip, library dependencies, ownership and APT consistency passed. Tools have no setuid/setgid bits. Recheck these ABI providers when changing the Ubuntu base.

The source archive matches kernel.org's published SHA-256 `fbd62a100ab7bb8746ba0661255c3c48185b1e9021507c624da01fbc696330ec`. The checksum manifest's signature was not independently verified. Builder static archives support upstream test helpers; only shared libraries and the three utility executables are shipped in the runtime packages.

Removed Xvfb and xserver-common, addressing two inherited High occurrences for [CVE-2023-5574](https://security-tracker.debian.org/tracker/CVE-2023-5574). LMS browser and document checks pass headlessly without Xvfb. Related X client libraries remain; this does not exempt them from other advisories.

Verified three specific affected implementations are absent across `/usr`, `/opt`, `/ms-playwright` and `/app`:

| Advisory | Affected implementation absent | Inherited High occurrences |
| --- | --- | ---: |
| [CVE-2026-24882](https://security-tracker.debian.org/tracker/CVE-2026-24882) | GnuPG tpm2daemon PKDECRYPT | 7 |
| [CVE-2026-52490](https://security-tracker.debian.org/tracker/CVE-2026-52490) | tiffcrop executable/tool code | 1 |
| [CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) | Perl Archive::Tar module; import also fails with module-not-found | 1 |

GnuPG, TIFF and Perl were not upgraded in this batch. These assessments apply only to those exact advisories and this image.

## Candidate and validation

Selected tag: `lms-sbom-backend:candidate-20261006-16`.

Exact image ID: `sha256:745b3418f4009f8b832beb630b49718893eb4a7dc9310307d0bc5951f6dbb827`.

VM evidence: `/home/karphi/lms-security/evidence/backend-high-candidate-20261006-16`. Local evidence copy: `tmp/security-20261006/backend-high-candidate-20261006-16`. The [candidate manifest](sbom-lms-candidate-manifest-2026-10-06.json) records identities, hashes, per-component database snapshots and prior candidates.

- Native LMS document conversion, embedded-image processing, browser slide capture, narration encoding, clip concatenation and fMP4 HLS checks passed with synthetic inputs, no network and no live mounts or credentials. The font-request substitution remains a test fixture.
- Upstream libmount tests: **85 sub-tests passed in seven groups; 11 groups skipped** because optional tools, Python bindings or privileges were unavailable. The driver's “all 18 passed” includes skips and must not be treated as 18 executed groups. Privileged mount exploitation tests were not run.
- Existing application tests: **44 passed, one failed**. The same slide-layout failure was reproduced on the prior candidate; it remains a release gate.
- Application import and `/health` route passed without running lifespan. **Full startup requires PostgreSQL and was not validated.** The earlier attempted startup probe incorrectly assumed a SQLite fallback; the application supports no such fallback. CMD/healthcheck configuration is preserved, but configuration is not startup proof.
- All 147 application/script context files, Dockerfile, dependency locks and package recipe match local hashes. Raw CycloneDX has 398 components; enriched inventory has 399, including manually added FFmpeg and native provenance. References were checked; full schema validation remains pending.

Both backend candidates were scanned with Trivy 0.75.0 against the same freshly frozen database, updated `2026-10-06T07:04:23.108323632Z`:

| Raw Ubuntu scanner matches | Previous candidate 15 | New candidate 16 |
| --- | ---: | ---: |
| Critical / High | 0 / 0 | 0 / 0 |
| Medium / Low | 25 / 14 | 25 / 12 |
| Total | 39 | 37 |

The raw change is two Xvfb occurrences rated Low by Ubuntu; the inherited register retains their original High ratings. The database refresh added one Medium PNG match to the previously reported 38: it appears on both candidates and concerns an already reviewed upstream fix in PNG 1.6.59. Raw PCRE2 and PNG matches remain unsuppressed. The [current register](sbom-lms-backend-current-round3-2026-10-06.csv) separates reviewed fixes from open raw matches. Neither the raw count nor its vendor coverage replaces the inherited register.

## Remaining High work and release gates

Fourteen inherited High occurrences remain: ACL (1), Expat (1), TIFF (1), libX11 (3), libXrender (1), cJSON (5), librsvg (1) and libsndfile (1). The last seven remain open for bundled-code review even though system paths are absent.

Python privately bundles **Expat 2.8.3**, and Pillow privately bundles **TIFF 4.7.1**. Future fixes must address both system and bundled copies. ACL changes need compatibility testing with tar; X client library advisories require supported upstream fixes or reviewed patches. Preserve unresolved findings and rerun affected checks after each coherent change.

All three live LMS application containers were verified healthy on their original image IDs. No services were restarted, PostgreSQL was not accessed, and no UAT deployment, commit or push was performed. Remaining risk review, the existing layout failure, full PostgreSQL startup and real Hub/course-flow validation still block release. Source-built components require ongoing maintenance; mutable APT/browser downloads prevent bit-for-bit reproducibility.
