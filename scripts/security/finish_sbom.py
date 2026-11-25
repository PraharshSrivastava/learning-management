"""Add supplier names and the bundled browser to a Trivy CycloneDX SBOM.

The raw SBOM is left untouched; the result is written to a new file. Supplier
names come from the image's own package metadata (see backend/security/write_notices.py
and the pnpm licence listing in deploy/web.Dockerfile), never from guesses. A
component whose ecosystem publishes no supplier keeps the field empty and is counted.

Usage: finish_sbom.py RAW_SBOM OUTPUT [--inventory third-party-inventory.json]
                                      [--npm-licences third-party-licenses.json]
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--npm-licences', type=Path)
    args = parser.parse_args()

    bom = json.loads(args.raw.read_text())
    inventory = json.loads(args.inventory.read_text()) if args.inventory else {}
    python = {row['name'].lower().replace('_', '-'): row['supplier'] for row in inventory.get('python', [])}
    system = {row['name']: row['supplier'] for row in inventory.get('os', [])}
    npm = {}
    if args.npm_licences:
        for rows in json.loads(args.npm_licences.read_text()).values():
            for row in rows:
                npm[row['name']] = row.get('author') or ''

    filled = empty = 0
    for component in bom.get('components', []):
        purl = component.get('purl', '')
        name = component.get('name', '')
        if purl.startswith('pkg:pypi/'):
            supplier = python.get(name.lower().replace('_', '-'), '')
        elif purl.startswith('pkg:deb/'):
            supplier = system.get(name, '')
        elif purl.startswith('pkg:apk/'):
            supplier = 'Alpine Linux'
        elif purl.startswith('pkg:npm/'):
            supplier = npm.get(name, '')
        else:
            supplier = ''
        if supplier and 'supplier' not in component:
            component['supplier'] = {'name': supplier}
        filled += 'supplier' in component
        empty += 'supplier' not in component

    for browser in inventory.get('browsers', []):
        bom.setdefault('components', []).append({
            'type': 'application',
            'bom-ref': f"browser:{browser['name']}@{browser['revision']}",
            'name': browser['name'],
            'version': browser['version'] or f"playwright-build-{browser['revision']}",
            'supplier': {'name': browser['supplier']},
            'properties': [
                {'name': 'lms:playwright-build', 'value': str(browser['revision'])},
                {'name': 'lms:path', 'value': browser['path']},
                {'name': 'lms:delivery', 'value': 'Installed at image build; never downloaded at run time'},
            ],
        })

    args.output.write_text(json.dumps(bom, indent=1))
    print(f"{args.output.name}: supplier set on {filled} components, not published for {empty}, "
          f"browsers recorded {len(inventory.get('browsers', []))}")


if __name__ == '__main__':
    main()
