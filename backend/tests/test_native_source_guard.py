import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('native_guard', Path(__file__).parents[1] / 'security' / 'check_native_bundle_lock.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.fixture
def fixture(tmp_path):
    source = '/site/lxml.so'
    downloaded = '/site/download.so'
    contents = {source: b'\x7fELFfresh-source-output', downloaded: b'\x7fELFfixed-wheel-output'}
    for name, data in contents.items():
        path = tmp_path / name.lstrip('/')
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
    manifest = {'schema': 1, 'package': 'lxml', 'version': '6.1.3', 'source_sha256': 'a' * 64,
                'wheel_sha256': 'b' * 64, 'native_files': {source: hashlib.sha256(contents[source]).hexdigest()}}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    lock = {'review_roots': ['/site'], 'source_builds': {'lxml': {'version': '6.1.3', 'source_sha256': 'a' * 64, 'manifest': '/manifest.json'}},
            'files': {source: {'sha256': 'c' * 64, 'owners': ['python:lxml==6.1.3']},
                      downloaded: {'sha256': hashlib.sha256(contents[downloaded]).hexdigest(), 'owners': ['downloaded']}}}
    return tmp_path, lock, manifest


def test_reviewed_source_rebuild_does_not_require_historical_binary_hash(fixture):
    root, lock, _ = fixture
    assert guard.verify(lock, root) == []


@pytest.mark.parametrize('mutation', ['source_hash', 'version', 'missing_manifest', 'extra_manifest_output', 'native_output', 'downloaded_output', 'new_native_file'])
def test_source_exception_cannot_accept_unreviewed_inputs_or_binary_changes(fixture, mutation):
    root, lock, manifest = fixture
    if mutation == 'source_hash':
        manifest['source_sha256'] = 'd' * 64
    elif mutation == 'version':
        manifest['version'] = '7.0.0'
    elif mutation == 'extra_manifest_output':
        manifest['native_files']['/site/new.so'] = 'e' * 64
    elif mutation == 'native_output':
        (root / 'site/lxml.so').write_bytes(b'\x7fELFtampered')
    elif mutation == 'downloaded_output':
        (root / 'site/download.so').write_bytes(b'\x7fELFtampered')
    elif mutation == 'new_native_file':
        (root / 'site/new.so').write_bytes(b'\x7fELFunreviewed')
    (root / 'manifest.json').write_text(json.dumps(manifest))
    if mutation == 'missing_manifest':
        (root / 'manifest.json').unlink()
    assert guard.verify(lock, root), mutation
