# LMS security evidence tools

These tools automate advisory checks and report grouping. They do not deploy images, accept risks, suppress findings, or prove exploitability.

## Scan a candidate batch on the VM

Run as the account that owns the evidence folder and can access Docker. Use a new report directory for every run. The script resolves each tag to its image ID before scanning, downloads advisory data once, serializes access to the selected cache, and scans all candidates against that same snapshot. Existing reports are preserved. Keep the original baseline database separately when using a refreshed cache.

```bash
export REPORT_DIR="$HOME/lms-security/evidence/release-review-<unique-run-id>"
export CACHE_DIR="$HOME/lms-security/cache-release-review"
export SCANNER_IMAGE="$(cat "$HOME/lms-security/scanner-image.txt")"
bash scripts/security/scan-candidates.sh \
  lms-sbom-backend:candidate-20261007-25 \
  lms-sbom-frontend:candidate-20261006-03 \
  lms-sbom-employee_frontend:candidate-20261006-03
```

The pinned scanner must already be available. The VM needs access to its advisory registry for the refresh. A failed download/scan exits with a nonzero status; do not interpret a missing report as zero findings. This script requires Bash and `flock`.

## Group findings and compare changes

Python 3 standard library is sufficient for these two commands. Run them on copied JSON reports or directly on the VM. Example:

```bash
python3 scripts/security/summarize_trivy.py candidate.json --output priorities.json
python3 scripts/security/compare_trivy.py before.json candidate.json --output comparison.json
```

`summarize_trivy.py` writes source-package remediation groups and a CSV retaining every occurrence, severity, advisory URL, listed fix and vendor status. Grouping is not a finding exemption. `compare_trivy.py` reports added/removed ecosystem-package-advisory occurrences and rejects different detected OS families; vendor coverage/severity changes cannot be counted as fixes. Verify scanner/database equivalence separately. Refresh-only changes must be reported separately from patch changes. Comparisons omit target paths and should use separate reports for each component.

## Audit hosted Dart packages

Use Python 3 with PyYAML, available in the existing backend development environment:

```powershell
& backend/.venv/Scripts/python.exe scripts/security/audit_pub.py frontend/pubspec.lock employee_frontend/pubspec.lock --output tmp/security-evidence/pub-audit.json
```

Only public pub.dev package names and exact versions are sent to OSV. Errors or paginated results fail instead of being interpreted as a clean audit. SDK/git/path packages are explicitly recorded as coverage gaps. Check that compiled `.dart_tool/package_config.json` matches the lockfile; a successful build with an overwritten lockfile alone is insufficient evidence. Frontend Dockerfiles now enforce locks with the compatible pinned SDK. These queries do not assess all Flutter/CanvasKit engine vulnerabilities or native plugin binaries.

Keep raw JSON and database metadata, review the critical/high families and supported fixes first, implement a coherent batch, and rerun only checks affected by the change. Generate release-linked SBOMs after the tested artifact set is finalized.

## Native candidate and inherited risk review

The selected backend native build and open release gates are recorded in [the round-two report](../../docs/security/sbom-lms-backend-remediation-round2-2026-10-06.md). XML, PCRE2 and PNG are operator-built packages; FFmpeg is a manually inventoried restricted build. These need upstream advisory review in addition to the Ubuntu package scan. Linux amd64 is the tested platform. Keep the raw scanner report unchanged.

`backend_native_smoke.py` checks the candidate's native document/video pipeline using synthetic inputs. Run it in a disposable container with `--network none --cap-drop=ALL --security-opt=no-new-privileges`, `PYTHONPATH=/app`, and only the script mounted read-only. Its font-request substitution is a test fixture, not proof of offline product behavior. `backend_native_inventory.py` asserts selected versions and code exclusions and outputs installed source-package versions and native file hashes. Never mount live storage, credentials or databases for these checks.

`fetch_ubuntu_vex.py` downloads commit-pinned official Ubuntu VEX into a new directory, records hashes/errors/missing records and lists unqueried non-CVE identifiers. Only public advisory IDs are queried. Missing, ignored, deferred or under-investigation statements are not fixes. `assess_ubuntu_vex.py` runs on a machine with `dpkg`; it verifies evidence hashes, selects Ubuntu 26.04 source-package statements and compares actual source versions:

```bash
python3 scripts/security/fetch_ubuntu_vex.py previous-report.json --output new-vex-evidence
python3 scripts/security/assess_ubuntu_vex.py previous-report.json candidate-report.json \
  native-inventory.json new-vex-evidence --output inherited-vendor-assessment.json
```

`reconcile_backend_native.py EVIDENCE_DIR UPSTREAM_REVIEW_JSON` overlays this batch's reviewed XML/FFmpeg thresholds and verified exclusions, retaining every other unresolved inherited row. It is intentionally specific to these native versions. `augment_backend_sbom.py EVIDENCE_DIR` writes a separate enriched CycloneDX file, annotates custom package maintenance/provenance and adds FFmpeg. It does not change the raw SBOM, scan for new advisories, or validate complete native coverage. Update the reviewed recipe/evidence when changing native versions; do not reuse a stale assessment as a future exemption.

## Reviewed High batch

`backend_high_inventory.py` extends the base inventory (mounted at `/checks/base-native.py`) with util-linux 2.42.4 runtime, package ownership, ABI compatibility, dependency and optional-component checks. `reconcile_backend_high.py PREVIOUS_INHERITED_CSV EVIDENCE_DIR` retains the full original register and overlays only four reviewed util-linux advisories, Xvfb removal and three specific affected-component absence assessments. It requires candidate image identity and preserved primary advisory review. These assessments differ from software upgrades and never edit Trivy output.

The four operator packages replace only libmount/libblkid/libuuid and mount/umount/nsenter. Their actual source/version is 2.42.4+lms1. Library packages provide the old Ubuntu 2.41.3-3ubuntu2.2 ABI to satisfy exact-version dependencies; this is a compatibility declaration, not the running code version. Other util-linux binaries remain at Ubuntu versions. Recheck dependency and ABI compatibility when the base changes. Static archives are built for upstream test helpers but are not shipped in runtime packages. Upstream test-driver summaries include skips; record actual pass/skip counts. Full application startup requires PostgreSQL; an import/health-route check without lifespan is not a startup test.

## Shared parser and X library batch

Earlier parser maintenance used candidate 17; see [the round-four report](../../docs/security/sbom-lms-backend-remediation-round4-2026-10-07.md). `backend_parser_smoke.py` verifies shared Expat/TIFF linkage, malformed UTF-16 rejection, image codecs, ACL no-follow behavior and tar compatibility in a disposable offline container. It records six-library ABI checks and native hashes. Pillow's distribution codec versions differ from its old private bundles; preserved functionality does not prove every codec advisory is fixed.

`reconcile_backend_parsers.py PREVIOUS_INHERITED_CSV EVIDENCE_DIR` preserves 829 rows and closes only seven named High occurrences with candidate identity, native package versions, parser/codec/ACL tests, smoke results and exact upstream X patch hashes. Other Expat/TIFF advisories and seven bundled-code High reviews remain open. Raw reports are unchanged. Rebuilding CPython or Pillow later must preserve their shared-parser configuration; repeat ABI and codec checks when changing the base. The tested incremental image does not replace the pending full repository rebuild or full-stack release gates.

The round-five parent is candidate21; see [round-five evidence](../../docs/security/sbom-lms-backend-remediation-round5-2026-10-07.md). `backend_medium_smoke.py` verifies the X/Expat/p11 maintenance libraries, Ubuntu PKCS#11 paths, shared fonts, GnuTLS initialization and absence of the advisory-specific Avahi/ACL server/tool components. `reconcile_backend_medium.py` updates only reviewed pairs and keeps six inherited High bundle reviews open. `backend/security/check_removed_components.py` fails on reintroduced cJSON/librsvg/libsndfile OS libraries or dynamic dependencies; it cannot prove absence of unidentified static copies.

## Backlog native batch

The native patch batch selected candidate24; see [round-six evidence](../../docs/security/sbom-lms-backend-remediation-round6-2026-10-07.md). Candidate21 remains its verified parent. `backend_backlog_smoke.py` checks actual ALSA/CUPS entry points, installed binary hashes, package dependencies and nscd absence. `backend_gpg_regression.py` reproduces the parent flaw with `--parent`, then requires both patched gpg/gpgv tools to reject forged cleartext while accepting valid signatures. Run only in disposable offline containers: it generates and deletes synthetic keys.

`reconcile_backend_backlog.py PREVIOUS_INHERITED_CSV PREVIOUS_CURRENT_CSV EVIDENCE_DIR` verifies pinned patch hashes, candidate identity, native/GnuPG/RTSP regression evidence and document/media smoke before overlaying 19 specific Medium assessments. It retains every other inherited row and keeps unmodified raw findings visible. Custom backports may remain flagged in raw vendor scans; no ignore rules are used. The raw same-database comparison has zero added and zero removed matches; the 19 closures are evidence-backed fixes/applicability reviews, not 19 disappearing scanner rows.

Native maintenance sources and limits are documented in [the backend security README](../../backend/security/README.md). Full current-checkout build and real Hub/course validation remain release gates. Changed live image IDs were observed during the interruption; candidate reports do not establish those live artifacts' vulnerability state. PostgreSQL remains deferred.

## Native bundled-code review

The historical incremental backend is candidate25; see [Priority 1 evidence](../../docs/security/sbom-lms-backend-priority1-2026-10-07.md). It preserves every native/application hash checked on candidate24 and adds a build-time identity guard. Six inherited High coverage assessments remain open; this batch does not claim a software fix or advisory closure.

`backend_bundle_inventory.py` inventories ELF/static archives, installed package attribution, hashes, dynamic dependencies and target-family fingerprints in an offline disposable image. Negative fingerprints are discovery evidence, not proof that stripped code is absent. `backend/security/check_native_bundle_lock.py --lock backend/security/native-bundle-lock.json` checks the recorded runtime identities; run inside the built image with the installed lock path. The combined release keeps 62 exact reference identities and validates seven source-built lxml outputs against their approved source/version/output manifest. Missing/additional files, changed reference identities or invalid source evidence require renewed review. The lock/manifest is not signed source authentication or a vulnerability exemption; all six inherited High coverage assessments remain open.

`enrich_backend_bundles.py PARENT_EVIDENCE CURRENT_EVIDENCE` requires the specific candidate24-to25 native/application equivalence proof, preserves raw inventory and prior native annotations, and separately records actual MuPDF/PDFium engine versions and hashes. It does not scan their advisories or authenticate their build sources. Do not reuse this batch-specific proof after changing an artifact. Full schema/licence and compiled-code coverage remain release work.

`pymupdf_installed_inventory.py` records the exact installed distribution payload without importing the PDF engine. `verify_pymupdf_wheel.py WHEEL INSTALLED_JSON RELEASE_JSON --console-script CONSOLE_JSON --output RESULT_JSON` compares published archive/file hashes, RECORD integrity, wheel/build metadata and the declared installer console wrapper. It verifies published-byte identity, not authenticated source/build provenance. See [the PyMuPDF origin review](../../docs/security/sbom-lms-pymupdf-origin-2026-10-07.md); the exact PyPI wheel currently has no available provenance attestation, and no advisory assessment was closed.
