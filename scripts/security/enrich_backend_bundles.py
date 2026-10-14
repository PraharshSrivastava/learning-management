"""Carry proven unchanged native annotations forward and inventory PDF engines.

Requires whole-native-file and application identity equivalence evidence. This
does not close advisory assessments, authenticate sources or scan the engines.
"""
import argparse
import hashlib
import json
from pathlib import Path
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path)
    parser.add_argument('current', type=Path)
    args = parser.parse_args()
    parent, root = args.parent, args.current
    proof = json.loads((root / 'native-identity-equivalence.json').read_text())
    assert proof['native_files_identical_to_candidate24'] == 1316
    assert proof['application_files_identical'] == 102
    assert not proof['target_family_fingerprints'] and not proof['inventory_errors']
    bom = json.loads((parent / 'backend.enriched.cdx.json').read_text())
    raw = json.loads((root / 'backend.raw.cdx.json').read_text())
    old_ref = bom['metadata']['component']['bom-ref']
    bom['metadata'] = raw['metadata']
    new_ref = bom['metadata']['component']['bom-ref']
    def key(component):
        return component['name'], component.get('version'), component.get('purl')
    previous = {key(c): c for c in bom['components']}
    assert len(previous) == len(bom['components']), 'Ambiguous component identity'
    assert {key(c) for c in raw['components']} <= set(previous)
    remap = {old_ref: new_ref}
    for component in raw['components']:
        prior = previous[key(component)]
        remap[prior['bom-ref']] = component['bom-ref']
        prior['bom-ref'] = component['bom-ref']
    for dependency in bom['dependencies']:
        dependency['ref'] = remap.get(dependency['ref'], dependency['ref'])
        dependency['dependsOn'] = [remap.get(ref, ref) for ref in dependency.get('dependsOn', [])]
    inventory = json.loads((root / 'bundle-inventory.json').read_text())
    hashes = {f['path']: f['sha256'] for f in inventory['files']}
    metadata = json.loads((root / 'build-metadata.json').read_text())
    engines = [
        ('mupdf', metadata['pymupdf'][1], '/usr/local/lib/python3.12/site-packages/pymupdf/libmupdf.so.29.0', 'pymupdf',
         'Runtime-reported engine version. Recorded PyMuPDF commit is public in pymupdf/PyMuPDF; public MuPDF development source reports 1.29.0 and 84 bundled headers match a pre-publication revision. Exact compiled MuPDF revision, generated bindings and transitive build inputs remain unauthenticated.'),
        ('pdfium', '.'.join(str(metadata['pdfium'][k]) for k in ('major', 'minor', 'build', 'patch')),
         '/usr/local/lib/python3.12/site-packages/pypdfium2_raw/libpdfium.so', 'pypdfium2',
         'Installed vendor build metadata reports version; commit hash is null. Branch dependency listing and binary hash do not authenticate exact compiled source.'),
    ]
    for name, version, path, owner, limitation in engines:
        ref = f'pkg:generic/{name}@{version}?lms_inventory=reported-native-engine'
        assert not any(c['bom-ref'] == ref for c in bom['components'])
        bom['components'].append({'type': 'library', 'name': name, 'version': version, 'bom-ref': ref, 'purl': ref,
            'hashes': [{'alg': 'SHA-256', 'content': hashes[path]}],
            'properties': [{'name': 'lms:runtime-file', 'value': path}, {'name': 'lms:provenance-limit', 'value': limitation},
                           {'name': 'lms:advisory-coverage', 'value': 'Manual inventory; this addition is not an advisory audit or finding closure'}]})
        owner_ref = next(c['bom-ref'] for c in bom['components'] if c['name'] == owner)
        dependency = next((d for d in bom['dependencies'] if d['ref'] == owner_ref), None)
        if dependency is None:
            dependency = {'ref': owner_ref, 'dependsOn': []}
            bom['dependencies'].append(dependency)
        dependency.setdefault('dependsOn', []).append(ref)
    bom['serialNumber'] = 'urn:uuid:' + str(uuid.uuid4())
    for prop in bom.get('properties', []):
        if prop['name'] == 'lms:raw-sbom-sha256':
            prop['value'] = hashlib.sha256((root / 'backend.raw.cdx.json').read_bytes()).hexdigest()
    bom.setdefault('properties', []).append({'name': 'lms:native-identity-equivalence-sha256',
        'value': hashlib.sha256((root / 'native-identity-equivalence.json').read_bytes()).hexdigest()})
    refs = {c['bom-ref'] for c in bom['components']} | {new_ref}
    assert all(d['ref'] in refs and set(d.get('dependsOn', [])) <= refs for d in bom['dependencies'])
    (root / 'backend.enriched.cdx.json').write_text(json.dumps(bom, indent=2) + '\n', encoding='utf8')
    print(f'Enriched {len(bom["components"])} components. No advisory closures; raw SBOM preserved.')


if __name__ == '__main__':
    main()
