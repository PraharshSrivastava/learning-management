"""Write the third-party notice file and a matching inventory for this image.

Runs at image build, using only the standard library. It lists every installed
Python distribution and OS package with its licence and supplier, and records the
browser build that Playwright installed. Full licence texts stay where the
packages put them; the notice file says where.

Usage: write_notices.py OUTPUT_DIR
"""
import email.header
import importlib.metadata
import json
import pathlib
import subprocess
import sys


def python_packages():
    rows = []
    for dist in importlib.metadata.distributions():
        meta = dist.metadata
        licence = meta.get('License-Expression') or meta.get('License') or ''
        if not licence or len(licence) > 120:
            # A long value is the full licence text; the classifier names it instead.
            names = [value.split(' :: ')[-1] for value in meta.get_all('Classifier') or []
                     if value.startswith('License ::')]
            licence = ', '.join(names) or 'See package metadata'
        supplier = (meta.get('Author') or meta.get('Maintainer') or meta.get('Author-email')
                    or meta.get('Maintainer-email') or '')
        supplier = _decoded(supplier)
        texts = sorted(str(path) for path in dist.files or []
                       if path.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')))
        rows.append({'name': meta['Name'], 'version': dist.version, 'licence': licence.strip(),
                     'supplier': supplier.strip(), 'licence_files': texts,
                     'location': str(dist.locate_file(''))})
    return sorted(rows, key=lambda row: row['name'].lower())


def _decoded(value):
    """Package metadata may encode non-ASCII names as =?utf-8?q?...?=; return plain text."""
    try:
        return str(email.header.make_header(email.header.decode_header(value)))
    except (ValueError, LookupError):
        return value


def os_packages():
    output = subprocess.check_output(
        ['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Maintainer}\n'], text=True)
    rows = []
    for line in output.splitlines():
        name, version, supplier = line.split('\t')
        copyright_file = pathlib.Path('/usr/share/doc') / name / 'copyright'
        rows.append({'name': name, 'version': version, 'supplier': supplier,
                     'copyright_file': str(copyright_file) if copyright_file.exists() else ''})
    return rows


def browsers():
    """Browser builds Playwright downloaded at image build, from its own manifest."""
    supplier = 'The Chromium Authors, built and distributed by Microsoft Playwright'
    installed = sorted(path.name for path in pathlib.Path('/ms-playwright').glob('*-*') if path.is_dir())
    known = {}
    try:
        import playwright
        manifest = pathlib.Path(playwright.__file__).parent / 'driver/package/browsers.json'
        for browser in json.loads(manifest.read_text())['browsers']:
            folder = f"{browser['name'].replace('-', '_')}-{browser['revision']}"
            known[folder] = browser.get('browserVersion', '')
    except (ImportError, OSError, ValueError, KeyError):
        pass  # The folder name still records the Playwright build number.
    rows = []
    for folder in installed:
        name, _, revision = folder.rpartition('-')
        rows.append({'name': name, 'revision': revision, 'version': known.get(folder, ''),
                     'supplier': supplier, 'path': f'/ms-playwright/{folder}'})
    return rows


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    inventory = {'python': python_packages(), 'os': os_packages(), 'browsers': browsers()}
    (out / 'third-party-inventory.json').write_text(json.dumps(inventory, indent=1))

    lines = [
        'THIRD-PARTY NOTICES - PhillipAcademy (LMS) backend image',
        '',
        'This image contains the third-party software listed below. Each component',
        'stays under its own licence. Licence texts ship inside the image at the',
        'locations given. Components under the LGPL (for example psycopg and several',
        'system libraries) are used as separate, unmodified, replaceable libraries.',
        '',
        f"PYTHON PACKAGES ({len(inventory['python'])})",
        'Licence texts: inside each package folder under the site-packages path shown.',
        '',
    ]
    for row in inventory['python']:
        lines.append(f"{row['name']} {row['version']} | {row['licence']} | {row['supplier'] or 'supplier not published'}")
        for text in row['licence_files']:
            lines.append(f"    {row['location']}/{text}")
    lines += ['', f"BROWSER ({len(inventory['browsers'])})", '']
    for row in inventory['browsers']:
        lines.append(f"{row['name']} {row['version']} (Playwright build {row['revision']}) | BSD-3-Clause and others | "
                     f"{row['supplier']} | {row['path']}")
    lines += ['', f"OPERATING SYSTEM PACKAGES ({len(inventory['os'])})",
              'Licence and copyright: /usr/share/doc/<package>/copyright', '']
    for row in inventory['os']:
        lines.append(f"{row['name']} {row['version']} | {row['supplier']}")
    (out / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(lines) + '\n')
    print(f"notices: {len(inventory['python'])} python, {len(inventory['os'])} os, "
          f"{len(inventory['browsers'])} browser")


if __name__ == '__main__':
    main()
