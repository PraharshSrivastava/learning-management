# Native backend maintenance patches

Keep the source/version metadata truthful. The Dockerfile pins archive and patch hashes, retains the matching Ubuntu patches where applicable, and builds custom maintenance packages. These packages require operator maintenance; do not infer that a distribution vendor supports the custom builds.

## Backlog patch sources

- `alsa-ctlparse.patch`: upstream [commit f84cd4c](https://github.com/alsa-project/alsa-lib/commit/f84cd4ced7b36fddb8e4ee24404cf7c091d27020), CVE-2026-90781.
- `alsa-sparse-bindings.patch`: narrow operator backport based on [ALSA PR527](https://github.com/alsa-project/alsa-lib/pull/527), CVE-2026-96675. Validate negative indices, slave bounds and channel bounds before allocating/indexing. Unrelated path-policy changes are excluded.
- `cups-utf32.patch`: fixed-width type hunk from accepted upstream [commit 2b1dc17](https://github.com/OpenPrinting/cups/commit/2b1dc178a2d2325135b855142e384f4e8c42d8e4), CVE-2026-87875. CUPS 2.4.16 Ubuntu patches and GSSAPI exports are preserved. Changing UTF-32 element width is intentional; retained SONAME/exports alone do not prove caller compatibility.
- `gnupg-cleartext.patch`: operator fail-closed guard for [CVE-2025-68972](https://security-tracker.debian.org/tracker/CVE-2025-68972), applied to both gpg and gpgv from matching Ubuntu source. Rejecting a truncated cleartext line prevents verification of lossy input. Legitimate cleartext lines reaching the existing parser limit are also rejected. This is not a claimed upstream release fix. Regression inputs follow the public [researcher demonstration](https://gpg.fail/formfeed), with ephemeral offline keys.

`package_backlog.py` checks CUPS/ALSA exports and SONAMEs; `package_backlog_extra.py` retains vendor-owned files, replacing only the reviewed gpg and gpgv binaries. Existing auxiliary libraries and tools retain their real vendor versions.

Use the regression tools under `scripts/security` and preserve their results alongside exact image IDs, source/patch hashes, build logs, scanner database metadata and unmodified raw reports. A patch file or successful compilation alone does not close a finding. A full checkout build and real Hub/course testing remain release gates.

## Native artifact identity guard

`native-bundle-lock.json` records 69 Python/browser native artifacts in the tested candidate24-to25 lineage. `check_native_bundle_lock.py` retains exact reference hashes for 54 artifacts. The seven lxml artifacts and the eight Pillow artifacts use a source-build policy: each manifest must match its pinned version (lxml 6.1.3, Pillow 13.0.0), its pinned source SHA-256 and the original file set, and installed bytes must match that build output. The Dockerfile enforces the source hashes with pip and records wheel/native hashes plus compiler/build-package evidence, and XML/XSLT config versions for lxml. Pillow moved to this policy with the Pillow 13.0.0 security upgrade; the reference hashes kept for its files are the Pillow 12.3.0 bytes of the reference image and are not used while the source-build manifest is valid. Changed reference bytes, changed source/version, invalid or missing manifests and missing/added native artifacts are rejected. A source-build manifest is build evidence, not a signed attestation or security approval. Recheck provenance and behavior before changing the policy or baseline. The six High cJSON/librsvg/libsndfile coverage assessments remain open because package attribution, fingerprints and binary identity do not authenticate complete compiled contents. See [the Priority 1 report](../../docs/security/sbom-lms-backend-priority1-2026-10-07.md).

## Retired backports (November 2026)

The GStreamer RTSP backport (CVE-2026-85150) and the Poppler bounds backport (CVE-2026-102620/93312/93313/93314) were removed. Ubuntu now ships the same fixes, and more: gst-plugins-base1.0 1.28.2-1ubuntu0.3 and later, poppler 26.01.0-2ubuntu0.3 (which also fixes CVE-2026-107705). Both old patches were checked against Ubuntu's current patch series and are already applied there. The image uses Ubuntu's packages, and a build step fails if an older or custom version is installed. The six RTSP regression cases still run, now against Ubuntu's library.
