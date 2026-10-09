"""Verify this High-remediation candidate's native components and code absence.

Supply the unchanged base-native inventory script as /checks/base-native.py.
Absent optional executables/modules justify their specific advisory assessments;
absent system library names alone do not establish absence of bundled code.
"""
import contextlib
import ctypes
import hashlib
import io
import json
import os
import pathlib
import runpy
import stat
import subprocess

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    runpy.run_path('/checks/base-native.py')
data = json.loads(buffer.getvalue())

def output(args):
    return subprocess.check_output(args, text=True)

mount = ctypes.CDLL('libmount.so.1')
mount.mnt_get_library_version.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
mount.mnt_get_library_version.restype = ctypes.c_int
version = ctypes.c_char_p()
mount.mnt_get_library_version(ctypes.byref(version))
assert version.value == b'2.42.4', version.value
blkid = ctypes.CDLL('libblkid.so.1')
blkid.blkid_get_library_version.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_char_p)]
blkid.blkid_get_library_version.restype = ctypes.c_int
date = ctypes.c_char_p()
blkid.blkid_get_library_version(ctypes.byref(version), ctypes.byref(date))
assert version.value == b'2.42.4', version.value
mount.mnt_new_table_from_file.argtypes = [ctypes.c_char_p]
mount.mnt_new_table_from_file.restype = ctypes.c_void_p
mount.mnt_table_get_nents.argtypes = [ctypes.c_void_p]
mount.mnt_table_get_nents.restype = ctypes.c_int
mount.mnt_free_table.argtypes = [ctypes.c_void_p]
table = mount.mnt_new_table_from_file(b'/proc/self/mountinfo')
assert table
assert mount.mnt_table_get_nents(table) > 0
mount.mnt_free_table(table)
uuid = ctypes.CDLL('libuuid.so.1')
uuid.uuid_generate_random.argtypes = [ctypes.c_void_p]
uuid.uuid_unparse.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
uuid.uuid_parse.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
uuid.uuid_parse.restype = ctypes.c_int
binary = ctypes.create_string_buffer(16)
parsed = ctypes.create_string_buffer(16)
text = ctypes.create_string_buffer(37)
uuid.uuid_generate_random(binary)
uuid.uuid_unparse(binary, text)
assert uuid.uuid_parse(text.value, parsed) == 0 and parsed.raw == binary.raw
commands = {}
for name in ('mount', 'umount', 'nsenter'):
    path = pathlib.Path('/usr/bin') / name
    commands[name] = output([str(path), '--version']).splitlines()[0]
    assert '2.42.4' in commands[name]
    assert not path.stat().st_mode & (stat.S_ISUID | stat.S_ISGID)
    assert 'lms-util-linux-security-tools' in output(['dpkg-query', '-S', str(path)])
    assert 'not found' not in output(['ldd', str(path)])
    data['file_sha256'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
for name in ('libmount.so.1', 'libblkid.so.1', 'libuuid.so.1'):
    path = (pathlib.Path('/usr/lib/x86_64-linux-gnu') / name).resolve()
    assert 'not found' not in output(['ldd', str(path)])
    data['file_sha256'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
for name in ('lms-libmount1', 'lms-libblkid1', 'lms-libuuid1', 'lms-util-linux-security-tools'):
    assert any(p['name']==name and p['version']=='2.42.4+lms1' for p in data['packages']), name
assert not any(p['name'] in ('xvfb', 'xserver-common') for p in data['packages'])
assert not pathlib.Path('/usr/bin/Xvfb').exists()
assert not output(['dpkg', '--audit']).strip()
subprocess.run(['apt-get', '-s', 'check'], check=True, stdout=subprocess.DEVNULL)
proof = {}
for needle in ('tpm2', 'tiffcrop', 'Archive/Tar.pm', 'cjson', 'librsvg', 'libsndfile'):
    found = [str(p) for base in ('/usr', '/opt', '/ms-playwright', '/app')
             for p in pathlib.Path(base).rglob('*') if needle.lower() in str(p).lower()]
    assert not found, (needle, found)
    proof[needle] = found
tar = subprocess.run(['perl', '-MArchive::Tar', '-e', 'print $Archive::Tar::VERSION'], capture_output=True, text=True)
assert tar.returncode != 0 and "Can't locate Archive/Tar.pm" in tar.stderr
data.update(util_linux_security_version='2.42.4', utility_versions=commands,
            new_libraries_compatible_with_old_utilities=output(['findmnt', '--json', '--target', '/']).strip().startswith('{'),
            uuid_roundtrip='PASS', native_mount_table_read='PASS', apt_dependency_check='PASS',
            setuid_security_tools=False, optional_component_paths=proof,
            archive_tar_import='Absent: module import fails with module-not-found',
            removal_scope='Xvfb packages and executable removed. TPM daemon, tiffcrop and Archive::Tar are absent. Missing cJSON/rsvg/sndfile system libraries remain open for bundled-code review.',
            current_cpython_expat=__import__('pyexpat').EXPAT_VERSION,
            current_pillow_libtiff=__import__('PIL.features', fromlist=['version']).version('libtiff'))
assert data['new_libraries_compatible_with_old_utilities']
print(json.dumps(data, indent=2))
