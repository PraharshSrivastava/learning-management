"""Assess the reviewed High batch without changing or suppressing scanner output.

Input: previous inherited CSV, candidate evidence directory. This deliberately
handles only named advisories with verified components, never whole families.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

UTIL = {'CVE-2026-76642', 'CVE-2026-78408', 'CVE-2026-78409', 'CVE-2026-78410'}
ABSENT = {
    ('gnupg2', 'CVE-2026-24882'): ('tpm2', 'tpm2daemon is absent; affected PKDECRYPT implementation is not shipped. GnuPG version itself was not upgraded.'),
    ('tiff', 'CVE-2026-52490'): ('tiffcrop', 'tiffcrop is absent; this advisory concerns tools/tiffcrop.c, not the installed libtiff library. Other TIFF advisories remain open.'),
    ('perl', 'CVE-2026-9538'): ('Archive/Tar.pm', 'Archive::Tar is absent and import fails with module-not-found. Perl itself was not upgraded.'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous_csv', type=Path)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    root = args.evidence
    inventory_path = root / 'native-inventory.json'
    inv = json.loads(inventory_path.read_text())
    assert inv['util_linux_security_version'] == '2.42.4'
    assert inv['apt_dependency_check'] == 'PASS'
    assert inv['native_mount_table_read'] == 'PASS'
    assert inv['new_libraries_compatible_with_old_utilities'] is True
    assert inv['setuid_security_tools'] is False
    assert inv['archive_tar_import'].startswith('Absent:')
    for name in ('mount', 'umount', 'nsenter'):
        assert '2.42.4' in inv['utility_versions'][name]
    names = {p['name'] for p in inv['packages']}
    assert not names & {'xvfb', 'xserver-common'}
    image = (root / 'image-id.txt').read_text().strip()
    inspection = json.loads((root / 'image-inspect.json').read_text())[0]
    assert inspection['Id'] == image
    review = json.loads((root / 'high-advisory-review.json').read_text())
    assert review['util_linux_source_sha256'] == 'fbd62a100ab7bb8746ba0661255c3c48185b1e9021507c624da01fbc696330ec'
    reviewed = {r['advisory'] for r in review['rows']}
    assert UTIL | {a for _, a in ABSENT} | {'CVE-2023-5574'} <= reviewed
    rows = list(csv.DictReader(args.previous_csv.open(newline='', encoding='utf-8')))
    changes = []
    for row in rows:
        row['prior_round2_assessment'] = row['assessment']
        if not row['assessment'].startswith('OPEN_'):
            continue
        original = row['assessment']
        source, advisory = row['source'], row['advisory']
        if source == 'util-linux' and advisory in UTIL:
            row.update(assessment='UPSTREAM_AFFECTED_COMPONENTS_FIXED_VERIFIED',
                       candidate_source_versions='2.41.3-3ubuntu2.2 (other utilities); 2.42.4+lms1 (reviewed affected components)',
                       notes='Affected mount/umount/nsenter and libmount code upgraded to upstream 2.42.4; hashes, versioned ABI exports and runtime compatibility checked. Other Ubuntu util-linux binaries retain their original versions. This closes only four reviewed advisories.')
        elif (source, advisory) in ABSENT:
            needle, note = ABSENT[(source, advisory)]
            assert inv['optional_component_paths'][needle] == []
            row.update(assessment='AFFECTED_COMPONENT_ABSENT_VERIFIED', notes=note)
        elif source == 'xorg-server' and advisory == 'CVE-2023-5574':
            row.update(assessment='AFFECTED_COMPONENT_REMOVED_VERIFIED',
                       candidate_source_versions='(absent: Xvfb and xserver-common removed)',
                       notes='Xvfb and xserver-common packages and Xvfb executable removed; headless browser and native document/video smoke tests pass. No upstream-version fix claimed.')
        else:
            continue
        assert row['severity'] == 'HIGH', row
        row['evidence_url'] = 'https://security-tracker.debian.org/tracker/' + advisory
        changes.append(dict(source=source, package=row['package'], advisory=advisory,
                            severity=row['severity'], assessment=row['assessment']))
    assert len(changes) == 47, len(changes)
    with (root / 'inherited-reconciled.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        'candidate_image': image,
        'inherited_occurrences': len(rows),
        'assessments': dict(collections.Counter(r['assessment'] for r in rows)),
        'open_original_severity': dict(collections.Counter(r['severity'] for r in rows if r['assessment'].startswith('OPEN_'))),
        'addressed_original_severity': dict(collections.Counter(r['severity'] for r in rows if not r['assessment'].startswith('OPEN_'))),
        'this_batch': dict(collections.Counter(r['assessment'] for r in changes)),
        'changes': changes,
        'previous_register_sha256': hashlib.sha256(args.previous_csv.read_bytes()).hexdigest(),
        'native_inventory_sha256': hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        'advisory_review_sha256': hashlib.sha256((root / 'high-advisory-review.json').read_bytes()).hexdigest(),
        'limitations': 'Package-advisory occurrences, not unique CVEs. Distinguish upgrades, removal and applicability assessments. No scanner suppression. Bundled-code review and remaining inherited risks are still open. No deployment.'
    }
    (root / 'inherited-reconciled.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'changes'}, indent=2))


if __name__ == '__main__':
    main()
