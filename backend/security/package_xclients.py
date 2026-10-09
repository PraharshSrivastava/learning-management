"""Package the patched X clients, requiring unchanged SONAME and ELF exports."""
import json
from pathlib import Path
import shutil
import subprocess
import os

specs = [
    ('libx11-6', 'libx11', '2:1.8.13+lms2', 'libX11.so.6', 'libc6 (>= 2.38), libxcb1, libx11-data', 'libX11-1.8.13/COPYING'),
    ('libx11-xcb1', 'libx11', '2:1.8.13+lms2', 'libX11-xcb.so.1', 'libx11-6 (= 2:1.8.13+lms2)', 'libX11-1.8.13/COPYING'),
    ('libxi6', 'libxi', '2:1.8.2+lms1', 'libXi.so.6', 'libc6 (>= 2.38), libx11-6, libxext6, libxfixes3', 'libXi-1.8.2/COPYING'),
]
if os.environ.get('LMS_NATIVE_BATCH') == 'expat':
    specs = [('libexpat1', 'expat', '2.8.5+lms2', 'libexpat.so.1', 'libc6 (>= 2.38)', 'expat-2.8.5/expat/COPYING')]
elif os.environ.get('LMS_NATIVE_BATCH') == 'p11-kit':
    specs = [('libp11-kit0', 'p11-kit', '0.26.5+lms1', 'libp11-kit.so.0', 'libc6 (>= 2.38), libffi8', 'p11-kit-0.26.5/COPYING')]
root = Path('/medium-install/usr/lib/x86_64-linux-gnu')
out = Path('/medium-out')
out.mkdir(exist_ok=True)
proof = []
def exports(path):
    return {line.split()[-1].replace('@@', '@') for line in subprocess.check_output(['nm','-D','--defined-only',str(path)], text=True).splitlines() if line.strip()}
for name, source, version, soname, deps, license_path in specs:
    old = Path('/usr/lib/x86_64-linux-gnu') / soname
    new = root / soname
    missing = sorted(exports(old) - exports(new))
    assert not missing, (name, missing)
    dynamic = subprocess.check_output(['readelf','-d',str(new)], text=True)
    assert f'[{soname}]' in dynamic, (name, 'SONAME changed')
    package = Path('/medium-packages') / name
    libdir = package / 'usr/lib/x86_64-linux-gnu'
    libdir.mkdir(parents=True)
    for path in root.glob(soname + '*'):
        shutil.copy2(path, libdir / path.name, follow_symlinks=False)
    doc = package / 'usr/share/doc' / name
    doc.mkdir(parents=True)
    shutil.copy2(Path('/src') / license_path, doc / 'copyright')
    control = package / 'DEBIAN'
    control.mkdir()
    (control / 'control').write_text(f'Package: {name}\nSource: {source}\nVersion: {version}\nArchitecture: amd64\nMaintainer: LMS security maintainer\nSection: libs\nPriority: optional\nDepends: {deps}\nDescription: LMS upstream native security maintenance build\n')
    subprocess.run(['dpkg-deb','--build','--root-owner-group',str(package),str(out / (name+'.deb'))], check=True)
    proof.append(dict(package=name,version=version,soname=soname,missing_exports=missing))
(out / 'abi-check.json').write_text(json.dumps(proof,indent=2)+'\n')
