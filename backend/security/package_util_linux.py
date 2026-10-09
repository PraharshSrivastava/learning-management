"""Package only the reviewed util-linux libraries and security tools.

Other Ubuntu util-linux utilities deliberately retain their own package/version.
Do not claim a full source-family upgrade from this partial replacement.
"""
import pathlib
import os
import shutil
import subprocess

BASE = pathlib.Path('/src/util-linux-2.42.4')
LIBDIR = pathlib.Path('/install/usr/lib/x86_64-linux-gnu')
OUT = pathlib.Path('/out')
OUT.mkdir(exist_ok=True)


def symbols(path):
    output = subprocess.check_output(['nm', '-D', '--defined-only', str(path)], text=True)
    # Preserve required ELF version bindings, not just unversioned function names.
    return {line.split()[-1].replace('@@', '@') for line in output.splitlines() if line.split()}


def package(name, files, depends, replaces='', compatibility_provider=''):
    root = pathlib.Path('/packages') / name
    (root / 'DEBIAN').mkdir(parents=True)
    for source, relative in files:
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            dest.symlink_to(source.readlink())
        else:
            shutil.copy2(source, dest)
    doc = root / 'usr/share/doc' / name
    doc.mkdir(parents=True)
    shutil.copytree(BASE / 'Documentation/licenses', doc / 'licenses')
    shutil.copy2(BASE / 'COPYING', doc / 'COPYING')
    control = (f'Package: {name}\nSource: util-linux\nVersion: 2.42.4+lms1\nArchitecture: amd64\n'
               'Maintainer: LMS security maintainer\nSection: libs\nPriority: optional\n'
               f'Depends: {depends}\nDescription: Reviewed util-linux native security components\n')
    if replaces:
        control += f'Replaces: {replaces}\n'
    if compatibility_provider:
        # Ubuntu's existing utility binaries have exact-version Pre-Depends.
        # This is an ABI compatibility provider, not a claim about code version;
        # the real operator package/source version remains 2.42.4+lms1.
        control += (f'Provides: {compatibility_provider} (= 2.41.3-3ubuntu2.2)\n'
                    f'Conflicts: {compatibility_provider}\n'
                    f'Replaces: {compatibility_provider}\n')
    (root / 'DEBIAN/control').write_text(control)
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(root),
                    str(OUT / f'{name}_2.42.4+lms1_amd64.deb')], check=True)


for package_name, library, depends in (
    ('libuuid1', 'libuuid.so.1', 'libc6 (>= 2.38)'),
    ('libblkid1', 'libblkid.so.1', 'libc6 (>= 2.38)'),
    ('libmount1', 'libmount.so.1', 'libc6 (>= 2.38), lms-libblkid1 (>= 2.42.4), libselinux1'),
):
    old = pathlib.Path('/usr/lib/x86_64-linux-gnu') / library
    new = LIBDIR / library
    missing = symbols(old) - symbols(new)
    (OUT / f'{package_name}-missing-symbols.txt').write_text('\n'.join(sorted(missing)))
    assert not missing, (package_name, missing)
    files = [(p, pathlib.Path('usr/lib/x86_64-linux-gnu') / p.name)
             for p in LIBDIR.glob(library + '*')]
    assert len(files) >= 2, (library, files)
    package('lms-' + package_name, files, depends, compatibility_provider=package_name)

tools = []
for name in ('mount', 'umount', 'nsenter'):
    paths = [pathlib.Path('/install') / folder / name for folder in ('bin', 'sbin', 'usr/bin', 'usr/sbin')]
    paths = [p for p in paths if p.is_file() and not p.is_symlink() and p.read_bytes()[:4] == b'\x7fELF']
    assert len(paths) == 1, (name, paths)
    assert '2.42.4' in subprocess.check_output([str(paths[0]), '--version'], text=True,
                                             env=os.environ | {'LD_LIBRARY_PATH': str(LIBDIR)})
    paths[0].chmod(0o755)
    tools.append((paths[0], pathlib.Path('usr/bin') / name))
package('lms-util-linux-security-tools', tools,
        'libc6 (>= 2.38), lms-libmount1 (>= 2.42.4), libselinux1',
        replaces='util-linux, mount')
print('Versioned ABI exports retained; packaged three libraries and mount/umount/nsenter without setuid.')
