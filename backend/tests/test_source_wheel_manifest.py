import hashlib
import importlib.util
from pathlib import Path
import zipfile
import pytest

spec = importlib.util.spec_from_file_location('source_manifest', Path(__file__).parents[1] / 'security' / 'record_source_wheel.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize('case', ['valid', 'wrong_version', 'unsafe_path', 'no_native_outputs'])
def test_manifest_binds_only_the_expected_wheel_and_safe_native_output_paths(tmp_path, case):
    source_lock = tmp_path / 'source.lock'
    source_lock.write_text('lxml==6.1.3 --hash=sha256:' + 'a' * 64 + '\n')
    wheel = tmp_path / 'lxml-6.1.3-cp312-cp312-linux_x86_64.whl'
    version = '7.0.0' if case == 'wrong_version' else '6.1.3'
    data = b'not-native' if case == 'no_native_outputs' else b'\x7fELFreviewed-source-output'
    name = '../unexpected.so' if case == 'unsafe_path' else 'lxml/etree.so'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('lxml-6.1.3.dist-info/METADATA', f'Name: lxml\nVersion: {version}\n')
        archive.writestr(name, data)
    if case != 'valid':
        with pytest.raises(ValueError):
            builder.record(source_lock, tmp_path)
    else:
        manifest = builder.record(source_lock, tmp_path)
        assert manifest['source_sha256'] == 'a' * 64
        assert manifest['wheel_sha256'] == hashlib.sha256(wheel.read_bytes()).hexdigest()
        assert manifest['native_files'] == {'/usr/local/lib/python3.12/site-packages/lxml/etree.so': hashlib.sha256(data).hexdigest()}
