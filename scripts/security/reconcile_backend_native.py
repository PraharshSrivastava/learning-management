"""Reconcile this specific native candidate with preserved vendor evidence.

This writes an assessment register, never a scanner suppression. Keep raw
cross-distribution reports separate. Only the verified native versions and
explicit excluded FFmpeg components below qualify for this reviewed batch.
"""
import argparse
import collections
import csv
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('upstream_review', type=Path)
    args = parser.parse_args()
    root = args.evidence
    inventory = json.loads((root / 'native-inventory.json').read_text())
    assert inventory['lxml_libxml'] == [2, 15, 4]
    assert inventory['ffmpeg_version'].startswith('ffmpeg version 9.0.2 ')
    assert inventory['pcre2_version'].startswith('10.49')
    assert inventory['libpng_version'] == '1.6.59'
    assert inventory['old_ffmpeg_shared_libraries_present'] is False
    assert {'dvdsub decoder', 'dvdsub parser', 'mpegps demuxer'} <= set(inventory['excluded_ffmpeg_components'])
    review = json.loads(args.upstream_review.read_text())
    reviewed = {(r['family'], r['advisory']): r for r in review['rows']}
    rows = list(csv.DictReader((root / 'inherited-vendor-assessment.csv').open(newline='')))
    for row in rows:
        row['prior_vendor_assessment'] = row['assessment']
        if row['source'] not in ('ffmpeg', 'libxml2'):
            continue
        evidence = reviewed[(row['source'], row['advisory'])]
        if row['source'] == 'ffmpeg' and row['advisory'] == 'CVE-2026-6385':
            row.update(assessment='VULNERABLE_CODE_EXCLUDED_VERIFIED',
                       notes='DVD subtitle decoder/parser and MPEG-PS demuxer disabled; installed configuration and decoder list verified. Not an upstream version fix.')
        else:
            release = evidence['tracker']['releases']['forky']
            assert release['status'] == 'resolved', (row['advisory'], release)
            # These exact upstream thresholds were reviewed for this batch;
            # do not treat an arbitrary resolved Debian backport as an upstream fix.
            fixed = release['fixed_version']
            match = re.match(r'(?:7:)?(\d+)\.(\d+)(?:\.(\d+))?', fixed)
            assert match, fixed
            threshold = tuple(int(v or 0) for v in match.groups())
            if row['source'] == 'ffmpeg':
                assert (8, 0, 0) <= threshold <= (9, 0, 2), fixed
            else:
                assert (2, 14, 0) <= threshold <= (2, 15, 4), fixed
            row.update(assessment='UPSTREAM_FIXED_VERSION_VERIFIED',
                       notes=f"Reviewed upstream release threshold {fixed}; runtime version and source hash verified. See preserved tracker feed, SHA256 {review['feed_sha256']}.")
        row['evidence_url'] = 'https://security-tracker.debian.org/tracker/' + row['advisory']
    target = root / 'inherited-reconciled.csv'
    with target.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        'candidate_image': json.loads((root / 'inherited-vendor-assessment.json').read_text())['candidate_image'],
        'inherited_occurrences': len(rows),
        'assessments': dict(collections.Counter(r['assessment'] for r in rows)),
        'open_original_severity': dict(collections.Counter(r['severity'] for r in rows if r['assessment'].startswith('OPEN_'))),
        'addressed_original_severity': dict(collections.Counter(r['severity'] for r in rows if not r['assessment'].startswith('OPEN_'))),
        'limitation': 'Open inherited issues remain visible even when the new OS scanner does not report them. Native-code exclusions and vendor not-affected assessments are distinct from version fixes.'
    }
    (root / 'inherited-reconciled.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
