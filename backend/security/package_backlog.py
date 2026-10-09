"""Package the narrow ALSA/CUPS maintenance builds with verified ELF ABI."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

specs = [
    ('libasound2t64', 'alsa-lib', '1.2.15.3+lms1', 'libasound.so.2',
     'libasound2-data (>= 1.2.15.3-1ubuntu1.1), libc6 (>= 2.43)', 'alsa-lib-1.2.15.3/COPYING'),
    ('libcups2t64', 'cups', '2.4.16+lms1', 'libcups.so.2',
     'libavahi-client3, libavahi-common3, libc6 (>= 2.38), libgnutls30t64, libgssapi-krb5-2, zlib1g', 'cups-2.4.16/LICENSE'),
]
out = Path('/backlog-out')
out.mkdir(exist_ok=True)
proof = []

def exports(path):
    return {line.split()[-1].replace('@@', '@') for line in subprocess.check_output(
        ['nm', '-D', '--defined-only', str(path)], text=True).splitlines() if line.strip()}

for name, source, version, soname, deps, license_path in specs:
    root = Path('/backlog-install/usr/lib/x86_64-linux-gnu')
    old, new = Path('/usr/lib/x86_64-linux-gnu') / soname, root / soname
    missing = sorted(exports(old) - exports(new))
    assert not missing, (name, missing)
    dynamic = subprocess.check_output(['readelf', '-d', str(new)], text=True)
    assert f'[{soname}]' in dynamic, (name, 'SONAME changed')
    package = Path('/backlog-packages') / name
    libdir = package / 'usr/lib/x86_64-linux-gnu'
    libdir.mkdir(parents=True)
    for path in root.glob(soname + '*'):
        shutil.copy2(path, libdir / path.name, follow_symlinks=False)
    doc = package / 'usr/share/doc' / name
    doc.mkdir(parents=True)
    shutil.copy2(Path('/src') / license_path, doc / 'copyright')
    control = package / 'DEBIAN'
    control.mkdir()
    (control / 'control').write_text(
        f'Package: {name}\nSource: {source}\nVersion: {version}\nArchitecture: amd64\n'
        f'Maintainer: LMS security maintainer\nSection: libs\nPriority: optional\nDepends: {deps}\n'
        'Description: LMS native maintenance build with reviewed bounds checks\n', encoding='utf-8')
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(package), str(out / (name + '.deb'))], check=True)
    proof.append(dict(package=name, version=version, soname=soname, missing_exports=missing,
                      sha256=hashlib.sha256(new.read_bytes()).hexdigest(), dynamic=dynamic))
(out / 'abi-check.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
