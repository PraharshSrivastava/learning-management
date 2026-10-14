"""Bind native wheel outputs to the source lock enforced by pip during this build.

This records build evidence, not a vulnerability exemption or signed attestation.
"""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile


def record(source_lock, wheels):
    entries = [line.strip() for line in source_lock.read_text().splitlines()
               if line.strip() and not line.lstrip().startswith('#')]
    if len(entries) != 1:
        raise ValueError('Expected one reviewed source distribution')
    match = re.fullmatch(r'(\w+)==([\w.]+) --hash=sha256:([0-9a-f]{64})', entries[0])
    if not match:
        raise ValueError('Expected an exact version and source SHA-256')
    name, version, source_hash = match.groups()
    artifacts = list(wheels.glob(f'{name}-{version}-*.whl'))
    if len(artifacts) != 1:
        raise ValueError('Expected one compiled wheel')
    wheel = artifacts[0]
    native = {}
    with zipfile.ZipFile(wheel) as archive:
        metadata_files = [p for p in archive.namelist() if p.endswith('.dist-info/METADATA')]
        if len(metadata_files) != 1:
            raise ValueError('Wheel metadata missing or ambiguous')
        metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        if metadata['Name'].lower() != name.lower() or metadata['Version'] != version:
            raise ValueError('Wheel/source identity mismatch')
        for info in archive.infolist():
            path = Path(info.filename)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe wheel path')
            content = archive.read(info)
            if content[:4] == b'\x7fELF' or content[:8] == b'!<arch>\n':
                destination = '/usr/local/lib/python3.12/site-packages/' + path.as_posix()
                native[destination] = hashlib.sha256(content).hexdigest()
    if not native:
        raise ValueError('No native outputs recorded')
    return {'schema': 1, 'package': name, 'version': version,
            'source_sha256': source_hash, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
            'python': sys.version, 'native_files': native,
            'source_verification': 'pip wheel --require-hashes --no-binary, enforced by Dockerfile',
            'security_disposition': 'Build output identity only; open coverage reviews remain open.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-lock', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = record(args.source_lock, args.wheels)
    # Preserve build-environment evidence; dependency versions are not exemptions.
    result['compiler'] = subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0]
    result['xml2_config_version'] = subprocess.check_output(['xml2-config', '--version'], text=True).strip()
    result['xslt_config_version'] = subprocess.check_output(['xslt-config', '--version'], text=True).strip()
    result['build_packages'] = subprocess.check_output(
        ['dpkg-query', '-W', '-f=${Package}=${Version}\n'], text=True).splitlines()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
