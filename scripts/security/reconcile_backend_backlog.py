"""Close only this native batch's verified pairs, retaining the inherited backlog."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from summarize_trivy import summarize

PATCHES = {
    'alsa-ctlparse.patch': 'fc88545f165594e9e7119b3c934562fcc71a7c8b2f4c78999e85662e669d02af',
    'alsa-sparse-bindings.patch': '6f86774595e6ebf2594cab1949bbb9ae66dd90383fb6dffa9f757bd884b6ad7e',
    'cups-utf32.patch': '47eb967434d2dadd11c149245109f267a0016381b6edca4829355b8002f30688',
    'gnupg-cleartext.patch': '88af0682a98daa78f0407710af149e0283c1b54f98c71b7dbd6329be3f31d64a',
    'gstreamer-rtsp.patch': 'f9e46d40ac3aef03d553c57147f3963c902d6d4e968d313d061ecef4dad26d8f',
    'poppler-bounds.patch': '2a9396c466741958b159bb608b53f1d7983397f522b3b2abfcfe94b10ae5fb43',
    'poppler_abi_anchors.cc': '8c10b90468f35a4ff73728b692841d6e9cfdb65692b40fc1514d424eafeda0ab',
}
TARGETS = {}
for source, cves, version, note in [
    ('alsa-lib', ['CVE-2026-90781', 'CVE-2026-96675'], '1.2.15.3+lms1',
     'Ctlparse terminator bounds and pre-allocation multi-PCM binding checks; actual library entry points and unchanged exports checked.'),
    ('cups', ['CVE-2026-87875'], '2.4.16+lms1',
     'Exact Ubuntu source and existing patches preserved; accepted upstream fixed-width UTF-32 types backported. Guard-page over-read regression and Unicode conversion passed.'),
    ('gnupg2', ['CVE-2025-68972'], '2.4.8-4ubuntu3.1+lms1 (gpg and gpgv)',
     'Operator fail-closed cleartext-truncation guard in both gpg and gpgv, retaining Ubuntu patches. Both old verifiers accepted forged signatures; both patched verifiers reject them. Long cleartext lines at the parser limit are now rejected; other GnuPG utilities/data remain vendor files.'),
    ('gst-plugins-base1.0', ['CVE-2026-85150'], '1.28.2-1ubuntu0.1+lms1',
     'RTSP parser bounds hunk from fixed 1.28.7 backported to the existing library ABI. Six malformed/valid Digest and Basic cases passed against the installed library.'),
    ('poppler', ['CVE-2026-102620', 'CVE-2026-93312', 'CVE-2026-93313', 'CVE-2026-93314'],
     '26.01.0-2ubuntu0.1+lms1',
     'Four accepted upstream bounds/bitmap/overflow fixes adapted to SONAME 156, including the older void-returning JBIG2 API; Ubuntu patches and library exports preserved. Document smoke passed; exact upstream exploit corpus not available. Does not close 93311 or 93653.'),
]:
    for cve in cves:
        TARGETS[source, cve] = ('SECURITY_BACKPORT_VERIFIED', version, note)
TARGETS['glibc', 'CVE-2026-89092'] = (
    'AFFECTED_COMPONENT_ABSENT_VERIFIED', 'nscd absent',
    'Primary advisory requires the nscd service. Its package, executable and searched runtime paths/socket are absent. This does not close other libc advisories or claim a glibc upgrade.')


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    parser.add_argument('previous_current', type=Path)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    root = args.evidence
    for name, digest in PATCHES.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    proof = json.loads((root / 'backlog-smoke.json').read_text())
    assert proof['cups_guard_page'] == proof['dependency_check'] == 'PASS'
    assert not proof['nscd_package_installed'] and proof['nscd_executable'] is None and proof['nscd_paths'] == []
    assert {p['package'] for p in proof['extra_provenance']} == {'gpg', 'gpgv', 'libgstreamer-plugins-base1.0-0', 'libpoppler156'}
    gpg = json.loads((root / 'gpg-regression.json').read_text())
    assert gpg['normal_cleartext'] == gpg['formfeed_cleartext'] == gpg['binary_detached'] == 'PASS'
    assert len(gpg['forged']) == 12 and all(r['exit_code'] != 0 and not r['valid_signature'] for r in gpg['forged'])
    assert {r['verifier'] for r in gpg['forged']} == {'gpg', 'gpgv'}
    old = json.loads((root / 'gpg-parent.json').read_text())
    assert all(any(r['verifier'] == v and r['valid_signature'] for r in old['forged']) for v in ['gpg', 'gpgv'])
    assert json.loads((root / 'rtsp-regression.json').read_text()) == {'rtsp_digest_cases': 6, 'result': 'PASS'}
    assert 'All candidate dependency smoke checks passed.' in (root / 'smoke.log').read_text()
    image = (root / 'image-id.txt').read_text().strip()
    assert json.loads((root / 'image-inspect.json').read_text())[0]['Id'] == image
    rows = list(csv.DictReader(args.previous.open(newline='', encoding='utf-8')))
    changes = []
    for row in rows:
        row['prior_round5_assessment'] = row['assessment']
        key = row['source'], row['advisory']
        if row['assessment'].startswith('OPEN_') and key in TARGETS:
            status, version, note = TARGETS[key]
            assert row['severity'] == 'MEDIUM'
            row.update(assessment=status, candidate_source_versions=version, notes=note,
                       evidence_url='https://security-tracker.debian.org/tracker/' + row['advisory'])
            changes.append({k: row[k] for k in ['source', 'package', 'advisory', 'severity', 'assessment']})
    assert len(rows) == 829 and len(changes) == 19, len(changes)
    write_csv(root / 'inherited-reconciled.csv', rows)
    current_summary, current = summarize(json.loads((root / 'backend-candidate.json').read_text()))
    prior = {(r['source'], r['package'], r['advisory']): r for r in
             csv.DictReader(args.previous_current.open(newline='', encoding='utf-8'))}
    for row in current:
        key = row['source'], row['advisory']
        previous = prior.get((row['source'], row['package'], row['advisory']), {})
        row.update(assessment=previous.get('assessment', 'OPEN_REVIEW_REQUIRED'), notes=previous.get('notes', ''))
        if key in TARGETS:
            status, _, note = TARGETS[key]
            row.update(assessment=status, notes=note)
    if current:
        write_csv(root / 'current-register.csv', current)
    summary = dict(candidate_image=image, inherited_occurrences=len(rows), changes=changes,
        open_original_severity=dict(Counter(r['severity'] for r in rows if r['assessment'].startswith('OPEN_'))),
        current_raw_severity=current_summary['severity'],
        current_open_severity=dict(Counter(r['severity'] for r in current if r['assessment'].startswith('OPEN_'))),
        previous_register_sha256=hashlib.sha256(args.previous.read_bytes()).hexdigest(),
        limitations='Inherited and raw current counts differ. Custom source patches require maintenance. Six High provenance reviews stay open. No deployment or suppression.')
    (root / 'inherited-reconciled.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
