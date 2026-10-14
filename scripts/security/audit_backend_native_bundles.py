"""Collect bounded native-bundle evidence; absence of fingerprints is not proof.

This screening intentionally never closes an advisory. Stripped/static code can
omit names, and an embedded SBOM can be incomplete. Source provenance is still
required for the inherited cJSON/librsvg/libsndfile assessments.
"""
import hashlib
import json
import os
from pathlib import Path

NEEDLES = {
    'cjson': (b'cJSON_Parse', b'cJSON_Version', b'cJSON_Delete'),
    'librsvg': (b'rsvg_handle_new', b'rsvg_handle_render', b'librsvg'),
    'libsndfile': (b'libsndfile', b'sf_open_virtual', b'sf_open_fd'),
}
roots = ['/usr/local/lib', '/usr/lib', '/opt/ffmpeg', '/ms-playwright']
matches, sboms = [], []
count = 0
for root in roots:
    for directory, _, names in os.walk(root):
        for name in names:
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                continue
            if name.endswith(('.cdx.json', '.spdx.json')):
                try:
                    data = json.loads(path.read_text())
                    components = data.get('components', data.get('packages', []))
                    selected = [c for c in components if any(n in c.get('name','').lower() for n in NEEDLES)]
                    sboms.append(dict(path=str(path),component_count=len(components),selected_components=selected,
                                      sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                except (OSError,ValueError):
                    pass
            try:
                with path.open('rb') as stream:
                    if stream.read(4) != b'\x7fELF':
                        continue
                    stream.seek(0)
                    count += 1
                    found = set()
                    tail = b''
                    while chunk := stream.read(1024 * 1024):
                        combined = tail + chunk
                        for family, needles in NEEDLES.items():
                            if any(needle in combined for needle in needles):
                                found.add(family)
                        tail = combined[-128:]
                    if found:
                        matches.append(dict(path=str(path),families=sorted(found),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            except OSError:
                continue
print(json.dumps(dict(elf_files_screened=count,fingerprint_matches=matches,embedded_sboms=sboms,
                      limitations='Screening only. Zero fingerprints or missing embedded SBOM entries cannot prove absence of stripped or statically bundled code. No finding closed.'),indent=2))
