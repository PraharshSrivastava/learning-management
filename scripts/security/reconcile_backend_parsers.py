"""Close only seven named inherited High occurrences with candidate proof."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

TARGETS = {
    ('acl', 'CVE-2026-54369'): ('2.4.0+lms1', 'Upstream ACL 2.4.0 shared library; ordinary upstream tests, no-follow API and GNU tar ACL round-trip verified. Privileged/NFS tests excluded.'),
    ('expat', 'CVE-2026-93990'): ('2.8.5+lms1', 'Both system Expat and CPython pyexpat use shared Expat 2.8.5. Malformed UTF-16 rejection and valid supplementary Unicode verified through Expat and ElementTree.'),
    ('tiff', 'CVE-2026-36849'): ('4.7.2+lms1', 'System TIFF upgraded to 4.7.2; Pillow rebuilt from its pinned 12.3.0 source and linked to the same shared library. Previous private TIFF removed; codec/multipage and native document checks passed.'),
    ('libx11', 'CVE-2026-88806'): ('2:1.8.13+lms1 (library and XCB companion); 2:1.8.13-1 (unchanged data)', 'Pinned upstream MR309 bounds-check patch applied without fuzz to X11 1.8.13. ELF exports preserved; XCB exact dependency replaced consistently; upstream and headless browser checks passed. Data itself is not executable vulnerable code.'),
    ('libxrender', 'CVE-2026-88807'): ('1:0.9.12+lms1', 'Pinned upstream MR19 screen/subpixel bounds-check patch applied without fuzz to Xrender 0.9.12. Shared-library ELF exports preserved and native browser/document checks passed. Patch is not yet an upstream release.'),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    root = args.evidence
    proof = json.loads((root / 'parser-smoke.json').read_text())
    assert proof['xml_version'] == 'expat_2.8.5' and proof['tiff_version'] == '4.7.2'
    assert proof['malformed_utf16_rejected'] and proof['valid_utf16_preserved']
    assert proof['acl_tar_roundtrip'] == proof['acl_nofollow'] == 'PASS'
    inv = json.loads((root / 'native-inventory.json').read_text())
    versions = {p['name']: p['version'] for p in inv['packages']}
    for name, version in [('libacl1','2.4.0+lms1'), ('libexpat1','2.8.5+lms1'), ('libtiff6','4.7.2+lms1'),
                          ('libx11-6','2:1.8.13+lms1'), ('libx11-xcb1','2:1.8.13+lms1'), ('libxrender1','1:0.9.12+lms1')]:
        assert versions[name] == version, (name, versions.get(name))
    image = (root / 'image-id.txt').read_text().strip()
    assert json.loads((root / 'image-inspect.json').read_text())[0]['Id'] == image
    assert 'PASS:' in (root / 'smoke.log').read_text()
    for name, digest in [('libx11-CVE-2026-88806.patch','e3803e8f544f767819cad13eb313129a0db4b47feeced0e17428244359b5eddd'),
                         ('libxrender-CVE-2026-88807.patch','5ec7674c395a731dbeb7160bb65cb44f961d75e3eabcfff7b9568feb1d05e978')]:
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    rows = list(csv.DictReader(args.previous.open(newline='', encoding='utf-8')))
    changes = []
    for row in rows:
        row['prior_round3_assessment'] = row['assessment']
        key = row['source'], row['advisory']
        if not row['assessment'].startswith('OPEN_') or key not in TARGETS:
            continue
        assert row['severity'] == 'HIGH'
        version, note = TARGETS[key]
        row.update(assessment='UPSTREAM_SECURITY_PATCH_FIXED_VERIFIED' if key[0] in ('libx11','libxrender') else 'UPSTREAM_AFFECTED_COMPONENTS_FIXED_VERIFIED',
                   candidate_source_versions=version, notes=note,
                   evidence_url='https://security-tracker.debian.org/tracker/' + row['advisory'])
        changes.append(dict(source=row['source'],package=row['package'],advisory=row['advisory']))
    assert len(rows) == 829 and len(changes) == 7, (len(rows),len(changes))
    with (root / 'inherited-reconciled.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary = dict(candidate_image=image, inherited_occurrences=len(rows), changes=changes,
                   open_original_severity=dict(collections.Counter(r['severity'] for r in rows if r['assessment'].startswith('OPEN_'))),
                   assessments=dict(collections.Counter(r['assessment'] for r in rows)),
                   previous_register_sha256=hashlib.sha256(args.previous.read_bytes()).hexdigest(),
                   limitations='Inherited package-advisory occurrences, not unique CVEs; source builds and patches require maintenance. Seven bundled-code High reviews remain open. No deployment.')
    (root / 'inherited-reconciled.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
