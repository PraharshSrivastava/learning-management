# Combined release execution progress — 8 October 2026

- Baseline confirmed: GitHub main and big-coding checkout e5c42da include the Performance/Observer changes through 7402617. Running app/database image IDs and deployment overlay hashes are recorded separately.
- Original dirty SBOM checkout preserved. Snapshot ZIP SHA-256: 8cd5841d205641f7e1042d167b6540279e1ae92f1518b6bfd77f47f428c29a08.
- Integrated on isolated branch codex/lms-sbom-release, build-source commit 767d262. Compose retains both trusted edge configuration and security restrictions. Application feature source and Nginx templates have zero diff from e5c42da.
- Failed PDF source replacement excluded; PostgreSQL remediation deferred. No live service restart or UAT deployment performed.
- Local backend suite: 329 passed, 60 opt-in tests skipped, one pre-existing landscape slide assertion failure. Both the failing test and its implementation are unchanged from main.
- Disposable VM database tests: 41 passed. Seeded only lms_performance_demo with synthetic data; Performance SQL parity suite: 15 passed. These validate feature code with the test image dependencies, not the unfinished maintained backend runtime.
- Trainer tests on pinned Flutter SDK: 36 passed on both export attempts. Employee native-platform tests expose the existing browser-only import gap; browser-platform validation is in progress.
- All fresh image scans and full candidate-runtime/Hub/UAT acceptance remain pending until their recorded results exist. Historical security counts are not recertified by this integration.

## Canonical source export

The first Windows Git archive exported text with CRLF and was unsuitable for pinned Linux patches/scripts. Its source/evidence are retained under source-crlf and release-767d262-crlf on the VM; its attempted backend build was cancelled. Do not use that archive for release.

Export using explicit Git configuration:

```bash
git -c core.autocrlf=false -c core.eol=lf archive --format=tar.gz --output=release-source.tar.gz 767d262
```

Accepted archive SHA-256: d208d1f98f529b4c134d0745f220418999e5dfb27bdc88712884a06185879c3e. Shell and patch archive bytes were checked against Git blobs, and the VM verified the archive checksum before extraction. Added LF attributes protect future shell/security-input checkouts; this infrastructure policy does not alter feature code.

## Remaining gates

Finish the maintained backend build and review any native identity drift; generate final SBOMs/scans, retain residual coverage gaps, run native/media smoke tests and the real Hub workflow checks, evaluate the existing slide-layout test failure, then prepare the reviewed release/rollback bundle before UAT promotion. Candidate tests use dedicated data/storage and preserve the live database and edge aliases.
