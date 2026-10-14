"""Compare an installed inventory with a published PyMuPDF wheel.

Checks archive and file identities, not source provenance or vulnerability state.
"""
import argparse
import base64
import csv
import configparser
import hashlib
import io
import json
from pathlib import Path
import zipfile


def verify(wheel, installed, release, console):
    archive_sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert archive_sha == release['sha256'], 'Wheel archive differs from published digest'
    matched, missing, different, record_errors = [], [], [], []
    with zipfile.ZipFile(wheel) as archive:
        assert archive.testzip() is None, 'Wheel CRC check failed'
        members = {n for n in archive.namelist() if not n.endswith('/')}
        record = next(n for n in members if n.endswith('.dist-info/RECORD'))
        wheel_metadata_path = next(n for n in members if n.endswith('.dist-info/WHEEL'))
        assert archive.read(wheel_metadata_path).decode() == installed['wheel_metadata'], 'Installed wheel tags differ'
        source_build = archive.read('pymupdf/_build.py').decode()
        assert source_build == installed['build_metadata'], 'Installed build metadata differs'
        for name, digest, size in csv.reader(io.StringIO(archive.read(record).decode())):
            if not digest:
                assert name == record, 'Unexpected unhashed wheel member'
                continue
            mode, expected = digest.split('=', 1)
            assert mode == 'sha256', mode
            data = archive.read(name)
            actual_sha = hashlib.sha256(data).hexdigest()
            if base64.urlsafe_b64encode(bytes.fromhex(actual_sha)).decode().rstrip('=') != expected or len(data) != int(size):
                record_errors.append(name)
            local = installed['files'].get(name)
            if local is None:
                missing.append(name)
            elif local['sha256'] != actual_sha or local['size'] != len(data):
                different.append(name)
            else:
                matched.append(name)
        assert {name for name, _, _ in csv.reader(io.StringIO(archive.read(record).decode()))} == members, 'Unrecorded archive members'
        extras = sorted(set(installed['files']) - members)
        generated = [name for name in extras if name.endswith('.pyc') or name.endswith(('.dist-info/INSTALLER', '.dist-info/REQUESTED'))]
        entrypoint = '../../../bin/pymupdf'
        if entrypoint in extras:
            entries = configparser.ConfigParser()
            entries.read_string(archive.read(next(n for n in members if n.endswith('.dist-info/entry_points.txt'))).decode())
            module, function = entries['console_scripts']['pymupdf'].split(':')
            text = console['console_script']
            expected = f"#!/usr/local/bin/python\nimport sys\nfrom {module} import {function}\nif __name__ == '__main__':\n    sys.argv[0] = sys.argv[0].removesuffix('.exe')\n    sys.exit({function}())\n"
            assert text == expected, 'Console wrapper differs from expected installer template/declared entry point'
            assert hashlib.sha256(text.encode()).hexdigest() == installed['files'][entrypoint]['sha256'], 'Console wrapper identity changed'
            generated.append(entrypoint)
        unexpected = sorted(set(extras) - set(generated))
        native = [name for name in matched if name.endswith(('.so', '.a')) or '.so.' in name]
        return {'filename': wheel.name, 'wheel_sha256': archive_sha,
                'archive_record_integrity': 'PASS' if not record_errors else 'FAIL',
                'installed_content_match': 'PASS' if not (missing or different or unexpected) else 'FAIL',
                'wheel_members': len(members), 'matched_payload_files': len(matched),
                'matched_native_files': native, 'missing': missing, 'different': different,
                'record_errors': record_errors, 'generated_installation_files': generated, 'unexpected_installed_files': unexpected,
                'record_note': 'Installed RECORD is rewritten by the installer; wheel RECORD was independently checked and every hashed wheel payload compared.',
                'published_build_metadata': source_build,
                'limitations': 'Published artifact identity only. No source/build attestation or vulnerability/non-applicability claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('installed', type=Path)
    parser.add_argument('release', type=Path)
    parser.add_argument('--console-script', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.wheel, json.loads(args.installed.read_text()), json.loads(args.release.read_text()), json.loads(args.console_script.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('generated_installation_files','published_build_metadata')}, indent=2))
    raise SystemExit(result['installed_content_match'] != 'PASS' or result['archive_record_integrity'] != 'PASS')
