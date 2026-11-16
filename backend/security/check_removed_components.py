"""Fail if removed OS libraries or their dynamic dependencies return.

This proves removal of the original OS components. It does not prove absence of
unidentified stripped/static copies in third-party binaries.
"""
import json
import os
from pathlib import Path
import struct
import subprocess

forbidden_packages = {'libcjson1', 'librsvg2-2', 'librsvg2-common', 'libsndfile1'}
families = {'cjson', 'librsvg', 'libsndfile'}
packages = subprocess.check_output(['dpkg-query','-W','-f=${binary:Package}\t${db:Status-Status}\n'],text=True)
installed = {line.split('\t')[0].split(':')[0] for line in packages.splitlines() if line.endswith('\tinstalled')}
assert not installed & forbidden_packages, sorted(installed & forbidden_packages)

def needed(path):
    """Read DT_NEEDED directly; no build tools are added to the runtime."""
    with path.open('rb') as stream:
        header = stream.read(64)
        if header[:4] != b'\x7fELF':
            return None
        assert header[4:6] == b'\x02\x01', ('unreviewed ELF architecture', str(path))
        offset = struct.unpack_from('<Q',header,32)[0]
        size, count = struct.unpack_from('<HH',header,54)
        stream.seek(offset)
        ph = [struct.unpack('<IIQQQQQQ',stream.read(size)[:56]) for _ in range(count)]
        loads = [h for h in ph if h[0] == 1]
        dyn = next((h for h in ph if h[0] == 2), None)
        if dyn is None:
            return []
        stream.seek(dyn[2])
        entries = []
        for _ in range(dyn[5] // 16):
            tag, value = struct.unpack('<qQ',stream.read(16))
            if tag == 0:
                break
            entries.append((tag,value))
        names = [v for t,v in entries if t == 1]
        if not names:
            return []
        address = next(v for t,v in entries if t == 5)
        segment = next(h for h in loads if h[3] <= address < h[3]+h[5])
        file_offset = segment[2] + address - segment[3]
        results = []
        for n in names:
            stream.seek(file_offset+n)
            b = bytearray()
            while c := stream.read(1):
                if c == b'\0':
                    break
                b.extend(c)
                assert len(b) < 4096, str(path)
            results.append(b.decode())
        return results

count = 0
violations = []
for root in ['/usr','/opt','/ms-playwright']:
    for directory, _, names in os.walk(root):
        for name in names:
            path = Path(directory)/name
            if any(name.lower().startswith(prefix) for prefix in ['libcjson.so','librsvg-', 'librsvg.so','libsndfile.so']):
                violations.append(dict(path=str(path),reason='forbidden library filename'))
            if path.is_symlink() or not path.is_file():
                continue
            deps = needed(path)
            if deps is None:
                continue
            count += 1
            for dep in deps:
                if any(family in dep.lower() for family in families):
                    violations.append(dict(path=str(path),dependency=dep))
assert not violations, violations
config = Path('/opt/ffmpeg/share/config_components.h').read_text()
assert '#define CONFIG_LIBRSVG_DECODER 0' in config
print(json.dumps(dict(original_os_components_absent=sorted(forbidden_packages),elf64_files_checked=count,
                      forbidden_dynamic_dependencies=violations,ffmpeg_librsvg_decoder=False,
                      limitations='Exact original OS components and dynamic dependencies only. Unknown static/private component provenance remains a separate open coverage gap.'),indent=2))
