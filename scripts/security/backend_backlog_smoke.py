"""Exercise the actual patched shared-library entry points, offline."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

ptr = C.c_void_p
cups = C.CDLL('libcups.so.2')
cups.cupsUTF32ToUTF8.argtypes = [C.POINTER(C.c_ubyte), C.POINTER(C.c_uint32), C.c_int]
# Place the 32-bit NUL at the end of a readable page; the next page is protected.
# The old 64-bit source stride reads the protected page. The fixed code reads 32-bit units.
libc = C.CDLL(None, use_errno=True)
libc.mmap.restype = ptr
libc.mmap.argtypes = [ptr, C.c_size_t, C.c_int, C.c_int, C.c_int, C.c_long]
libc.mprotect.argtypes = [ptr, C.c_size_t, C.c_int]
libc.munmap.argtypes = [ptr, C.c_size_t]
page = 4096
base = libc.mmap(None, 2 * page, 3, 0x22, -1, 0)
assert base and base != C.c_void_p(-1).value
assert libc.mprotect(base + page, page, 0) == 0
source = C.cast(base + page - 8, C.POINTER(C.c_uint32))
source[0], source[1] = 0x41, 0
dest = (C.c_ubyte * 32)()
assert cups.cupsUTF32ToUTF8(dest, source, len(dest)) == 1
assert bytes(dest).split(b'\0')[0] == b'A'
assert libc.munmap(base, 2 * page) == 0
for values, expected in [([0x41, 0x20AC, 0], 'A\u20ac'), ([0x1F600, 0], '\U0001f600')]:
    source = (C.c_uint32 * len(values))(*values)
    assert cups.cupsUTF32ToUTF8(dest, source, len(dest)) == len(expected.encode())
    assert bytes(dest).split(b'\0')[0] == expected.encode()

proof = json.loads(Path('/usr/share/lms-security/backlog-abi-check.json').read_text())
for entry in proof:
    assert entry['missing_exports'] == []
    library = Path('/usr/lib/x86_64-linux-gnu') / entry['soname']
    assert hashlib.sha256(library.read_bytes()).hexdigest() == entry['sha256']
    version = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', entry['package']], text=True)
    assert version == entry['version']
subprocess.run(['apt-get', '-s', 'check'], check=True, stdout=subprocess.DEVNULL)
assert not subprocess.check_output(['dpkg', '--audit'], text=True).strip()
extra = []
for path in ['/usr/share/lms-security/backlog-extra-provenance.json',
             '/usr/share/lms-security/poppler-maintenance.json']:
    if Path(path).exists():
        for entry in json.loads(Path(path).read_text()):
            assert entry['missing_exports'] == []
            assert hashlib.sha256(Path(entry['replaced_file']).read_bytes()).hexdigest() == entry['sha256']
            assert subprocess.check_output(['dpkg-query', '-W', '-f=${Version}',
                entry['package']], text=True) == entry['version']
            extra.append(entry)
nscd = subprocess.run(['dpkg-query', '-s', 'nscd'], capture_output=True, text=True)
assert 'Status: install ok installed' not in nscd.stdout
assert shutil.which('nscd') is None
nscd_paths = [str(p) for root in ['/usr', '/opt', '/app', '/run', '/var/run']
              for p in Path(root).rglob('nscd')]
assert not nscd_paths, nscd_paths
print(json.dumps(dict(cups_guard_page='PASS', cups_unicode='PASS',
    abi=proof, extra_provenance=extra, nscd_package_installed=False,
    nscd_executable=None, nscd_paths=nscd_paths, dependency_check='PASS'), indent=2))
