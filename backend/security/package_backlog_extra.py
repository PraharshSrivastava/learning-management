"""Retain vendor package files; replace only the reviewed GPG/RTSP binaries."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

out = Path('/extra-out')
out.mkdir(exist_ok=True)
proof = []
specs = [
    ('gpg', 'gnupg2', '2.4.8-4ubuntu3.1+lms1', '/usr/bin/gpg', '/src/gnupg-2.4.8/g10/gpg'),
    ('gpgv', 'gnupg2', '2.4.8-4ubuntu3.1+lms1', '/usr/bin/gpgv', '/src/gnupg-2.4.8/g10/gpgv'),
    ('libgstreamer-plugins-base1.0-0', 'gst-plugins-base1.0', '1.28.2-1ubuntu0.1+lms1',
     '/usr/lib/x86_64-linux-gnu/libgstrtsp-1.0.so.0.2802.0',
     '/src/gst-plugins-base-1.28.2/build/gst-libs/gst/rtsp/libgstrtsp-1.0.so.0.2802.0'),
]
if os.environ.get('LMS_EXTRA_BATCH') == 'poppler':
    specs = [('libpoppler156', 'poppler', '26.01.0-2ubuntu0.1+lms1',
        '/usr/lib/x86_64-linux-gnu/libpoppler.so.156.0.0', '/src/poppler-26.01.0/build/libpoppler.so.156.0.0')]
for name, source, version, target, replacement in specs:
    root = Path('/extra-packages') / name
    root.mkdir(parents=True)
    owned = subprocess.check_output(['dpkg-query', '-L', name], text=True).splitlines()
    retained_files = 0
    for entry in owned:
        path = Path(entry)
        if not path.is_file() and not path.is_symlink():
            continue
        dest = root / entry.lstrip('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest, follow_symlinks=False)
        retained_files += 1
    old, new = Path(target), Path(replacement)
    assert old.exists() and new.exists(), (str(old), str(new))
    dynamic = subprocess.check_output(['readelf', '-d', str(new)], text=True)
    missing = []
    if name.startswith('lib'):
        def exports(path):
            return {line.split()[-1].replace('@@', '@') for line in subprocess.check_output(
                ['nm', '-D', '--defined-only', str(path)], text=True).splitlines() if line.strip()}
        missing = sorted(exports(old) - exports(new))
        assert missing == [], missing
        assert ('[libpoppler.so.156]' if name == 'libpoppler156' else '[libgstrtsp-1.0.so.0]') in dynamic
    shutil.copy2(new, root / target.lstrip('/'))
    control = root / 'DEBIAN'
    control.mkdir()
    raw = subprocess.check_output(['dpkg-query', '-s', name], text=True)
    # Only stable control fields; remove installed-state/conffile metadata.
    allowed = {'Package', 'Source', 'Version', 'Architecture', 'Maintainer', 'Section', 'Priority',
               'Depends', 'Pre-Depends', 'Recommends', 'Suggests', 'Breaks', 'Replaces', 'Provides', 'Description', 'Multi-Arch'}
    lines, keep = [], False
    for line in raw.splitlines():
        if line.startswith(' '):
            if keep:
                lines.append(line)
            continue
        key = line.partition(':')[0]
        keep = key in allowed
        if not keep:
            continue
        if key == 'Version':
            line = f'Version: {version}'
        elif key == 'Source':
            line = f'Source: {source} ({version})'
        lines.append(line)
    (control / 'control').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    note = root / 'usr/share/doc' / name / 'lms-maintenance.json'
    note.parent.mkdir(parents=True, exist_ok=True)
    record = dict(package=name, version=version, replaced_file=target, missing_exports=missing,
                  sha256=hashlib.sha256(new.read_bytes()).hexdigest(),
                  unchanged_owned_files=retained_files - 1, dynamic=dynamic)
    note.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(root), str(out / (name + '.deb'))], check=True)
    proof.append(record)
(out / 'provenance.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
