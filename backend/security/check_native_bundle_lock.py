"""Reject changes to recorded downloaded native binaries pending a new review.

The lock records identity, not absence of vulnerabilities or authenticated build
provenance. Its open High assessments must remain open until separately proved.
"""
import argparse
import hashlib
import json
from pathlib import Path


def verify(lock, root):
    expected = lock['files']
    errors = []
    for name, record in expected.items():
        path = root / name.lstrip('/')
        if not path.is_file():
            errors.append({'path': name, 'reason': 'recorded native file missing'})
        elif hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            errors.append({'path': name, 'reason': 'native bytes changed; renewed review required'})
    for prefix in lock['review_roots']:
        directory = root / prefix.lstrip('/')
        if not directory.is_dir():
            errors.append({'path': prefix, 'reason': 'reviewed bundle directory missing'})
            continue
        for path in directory.rglob('*'):
            if path.is_symlink() or not path.is_file():
                continue
            with path.open('rb') as stream:
                magic = stream.read(8)
            if magic[:4] == b'\x7fELF' or magic == b'!<arch>\n':
                name = '/' + path.relative_to(root).as_posix()
                if name not in expected:
                    errors.append({'path': name, 'reason': 'new native file requires attribution and review'})
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path('/'))
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text())
    errors = verify(lock, args.root)
    print(json.dumps({'identity_check': 'FAIL' if errors else 'PASS', 'recorded_files': len(lock['files']),
                      'errors': errors, 'security_disposition': lock['security_disposition']}, indent=2))
    raise SystemExit(bool(errors))
