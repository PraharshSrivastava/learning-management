"""Check downloaded identities and outputs of explicitly approved source builds.

Source-build manifests bind outputs to reviewed source locks enforced by the
Dockerfile. They are build evidence, not signed attestations or CVE exemptions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def source_outputs(lock, root, errors):
    approved = {}
    for name, policy in lock.get('source_builds', {}).items():
        manifest_path = root / policy['manifest'].lstrip('/')
        try:
            manifest = json.loads(manifest_path.read_text())
            if not isinstance(manifest, dict):
                raise ValueError('Source-build manifest must be an object')
            owner = f"python:{name}=={policy['version']}"
            expected_paths = {path for path, record in lock['files'].items()
                              if record.get('owners') == [owner]}
            outputs = manifest.get('native_files', {})
            valid = (isinstance(outputs, dict) and manifest.get('schema') == 1 and manifest.get('package') == name
                     and manifest.get('version') == policy['version']
                     and manifest.get('source_sha256') == policy['source_sha256']
                     and re.fullmatch('[0-9a-f]{64}', manifest.get('wheel_sha256', ''))
                     and expected_paths and set(outputs) == expected_paths
                     and all(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest)
                             for digest in outputs.values()))
            if not valid:
                raise ValueError('Source identity or native output set is not approved')
            approved.update(outputs)
        except (OSError, ValueError, TypeError) as error:
            errors.append({'path': policy['manifest'], 'reason': f'Invalid source-build evidence: {error}'})
    return approved


def verify(lock, root):
    expected = lock['files']
    errors = []
    compiled = source_outputs(lock, root, errors)
    for name, record in expected.items():
        path = root / name.lstrip('/')
        if not path.is_file():
            errors.append({'path': name, 'reason': 'recorded native file missing'})
        elif hashlib.sha256(path.read_bytes()).hexdigest() != compiled.get(name, record['sha256']):
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
    compiled = source_outputs(lock, args.root, [])
    print(json.dumps({'identity_check': 'FAIL' if errors else 'PASS', 'recorded_files': len(lock['files']),
                      'source_build_files': len(compiled), 'reference_identity_files': len(lock['files']) - len(compiled),
                      'errors': errors, 'security_disposition': lock['security_disposition']}, indent=2))
    raise SystemExit(bool(errors))
