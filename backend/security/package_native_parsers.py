"""Package reviewed native builds with truthful versions and checked ELF ABI.

The original distribution owns all unrelated executables and data. Only the
shared libraries below are replaced, preserving their SONAME and ELF exports.
"""
import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path('/native-install/usr/lib/x86_64-linux-gnu')
OUT = pathlib.Path('/out')
OUT.mkdir(exist_ok=True)
SPECS = [
    ('libexpat1', 'expat', '2.8.5+lms1', ['libexpat.so.1*'], 'libexpat.so.1', 'libc6 (>= 2.38)', 'expat-2.8.5/expat/COPYING'),
    ('libtiff6', 'tiff', '4.7.2+lms1', ['libtiff.so.6*'], 'libtiff.so.6', 'libc6 (>= 2.38), libjpeg-turbo8, liblzma5, libzstd1, libwebp7, libjbig0, libdeflate0, liblerc4, zlib1g', 'tiff-4.7.2/LICENSE.md'),
    ('libacl1', 'acl', '2.4.0+lms1', ['libacl.so.1*'], 'libacl.so.1', 'libc6 (>= 2.38)', 'acl-2.4.0/doc/COPYING.LGPL'),
    ('libx11-6', 'libx11', '2:1.8.13+lms1', ['libX11.so.6*'], 'libX11.so.6', 'libc6 (>= 2.38), libxcb1, libx11-data', 'libX11-1.8.13/COPYING'),
    ('libx11-xcb1', 'libx11', '2:1.8.13+lms1', ['libX11-xcb.so.1*'], 'libX11-xcb.so.1', 'libx11-6 (= 2:1.8.13+lms1)', 'libX11-1.8.13/COPYING'),
    ('libxrender1', 'libxrender', '1:0.9.12+lms1', ['libXrender.so.1*'], 'libXrender.so.1', 'libc6 (>= 2.38), libx11-6', 'libXrender-0.9.12/COPYING'),
]

def exports(path):
    data = subprocess.check_output(['nm', '-D', '--defined-only', str(path)], text=True)
    return {line.split()[-1].replace('@@', '@') for line in data.splitlines() if line.strip()}

abi = []
for name, source, version, globs, soname, deps, license_path in SPECS:
    old = pathlib.Path('/usr/lib/x86_64-linux-gnu') / soname
    new = ROOT / soname
    missing = sorted(exports(old) - exports(new))
    assert not missing, (name, missing)
    package = pathlib.Path('/packages') / name
    libdir = package / 'usr/lib/x86_64-linux-gnu'
    libdir.mkdir(parents=True)
    for pattern in globs:
        for path in ROOT.glob(pattern):
            shutil.copy2(path, libdir / path.name, follow_symlinks=False)
    doc = package / 'usr/share/doc' / name
    doc.mkdir(parents=True)
    shutil.copy2(pathlib.Path('/src') / license_path, doc / 'copyright')
    control = package / 'DEBIAN'
    control.mkdir()
    (control / 'control').write_text(
        f'Package: {name}\nSource: {source}\nVersion: {version}\nArchitecture: amd64\n'
        f'Maintainer: LMS security maintainer\nSection: libs\nPriority: optional\nDepends: {deps}\n'
        'Description: LMS reviewed native security maintenance build\n')
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(package), str(OUT / (name + '.deb'))], check=True)
    abi.append(dict(package=name, source=source, version=version, missing_exports=missing, soname=soname))
(OUT / 'abi-check.json').write_text(json.dumps(abi, indent=2) + '\n')
