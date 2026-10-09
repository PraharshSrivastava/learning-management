"""Attribute native runtime files and locate evidence of the three High families.

Run in an offline disposable image. Fingerprint absence is explicitly not a
component-absence proof. No application storage or credentials are inspected.
"""
import base64
from collections import defaultdict
import hashlib
import importlib.metadata
import json
import mmap
import os
from pathlib import Path
import struct

ROOTS = ('/usr', '/opt', '/ms-playwright', '/app/app', '/app/scripts')
TOKENS = {
    'cjson': (b'cJSON_', b'cJSON.c', b'cJSON_Utils', b'libcjson'),
    'librsvg': (b'rsvg_handle_', b'librsvg', b'rsvg::'),
    'libsndfile': (b'sf_open', b'sf_readf_', b'libsndfile', b'sndfile.c', b'ima_adpcm.c'),
}


def elf_needed(data):
    if data[:4] != b'\x7fELF':
        return None
    if data[4:6] != b'\x02\x01':
        raise ValueError('ELF other than 64-bit little-endian requires review')
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    ph = [struct.unpack_from('<IIQQQQQQ', data, offset + i * size) for i in range(count)]
    loads = [h for h in ph if h[0] == 1]
    dyn = next((h for h in ph if h[0] == 2), None)
    if dyn is None:
        return []
    entries = []
    for off in range(dyn[2], dyn[2] + dyn[5], 16):
        tag, value = struct.unpack_from('<qQ', data, off)
        if tag == 0:
            break
        entries.append((tag, value))
    names = [v for t, v in entries if t == 1]
    if not names:
        return []
    address = next(v for t, v in entries if t == 5)
    segment = next(h for h in loads if h[3] <= address < h[3] + h[5])
    table = segment[2] + address - segment[3]
    return [data[table + n:data.find(b'\0', table + n)].decode() for n in names]


def inventory():
    owners = defaultdict(list)
    md5 = {}
    for listing in Path('/var/lib/dpkg/info').glob('*.list'):
        package = listing.name[:-5]
        for name in listing.read_text().splitlines():
            owners[name].append('dpkg:' + package)
            if name.startswith('/lib/'):
                owners['/usr' + name].append('dpkg:' + package)
    for listing in Path('/var/lib/dpkg/info').glob('*.md5sums'):
        for line in listing.read_text().splitlines():
            digest, name = line.split(None, 1)
            md5['/' + name] = digest
            if name.startswith('lib/'):
                md5['/usr/' + name] = digest
    wheel_hashes = {}
    distributions = []
    for dist in importlib.metadata.distributions():
        label = 'python:' + dist.metadata['Name'] + '==' + dist.version
        distributions.append(label)
        for item in dist.files or []:
            path = str(Path(dist.locate_file(item)).resolve())
            owners[path].append(label)
            if item.hash and item.hash.mode == 'sha256':
                wheel_hashes[path] = item.hash.value
    files, matches, errors = [], [], []
    visited = set()
    for root in ROOTS:
        for directory, _, names in os.walk(root):
            for name in names:
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file():
                    continue
                key = str(path)
                if key in visited:
                    continue
                visited.add(key)
                try:
                    with path.open('rb') as stream:
                        header = stream.read(8)
                        if header[:4] != b'\x7fELF' and header != b'!<arch>\n':
                            continue
                        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                            sha = hashlib.sha256(data).hexdigest()
                            proof = {'path': key, 'kind': 'ELF' if header[:4] == b'\x7fELF' else 'archive',
                                     'size': len(data), 'sha256': sha, 'owners': sorted(set(owners[key])),
                                     'needed': elf_needed(data), 'record_hash_match': None, 'dpkg_md5_match': None}
                            if key in wheel_hashes:
                                proof['record_hash_match'] = base64.urlsafe_b64encode(bytes.fromhex(sha)).decode().rstrip('=') == wheel_hashes[key]
                            if key in md5:
                                proof['dpkg_md5_match'] = hashlib.md5(data).hexdigest() == md5[key]
                            files.append(proof)
                            for family, tokens in TOKENS.items():
                                hits = [token.decode() for token in tokens if data.find(token) >= 0]
                                if hits:
                                    matches.append({'path': key, 'family': family, 'tokens': hits, 'owners': proof['owners'], 'sha256': sha})
                except Exception as exc:
                    errors.append({'path': key, 'error': str(exc)})
    return {'scope': list(ROOTS), 'files': files, 'matches': matches, 'errors': errors,
            'python_distributions': sorted(distributions),
            'counts': {'native_files': len(files), 'unowned': sum(not f['owners'] for f in files),
                       'record_mismatches': sum(f['record_hash_match'] is False for f in files),
                       'dpkg_mismatches': sum(f['dpkg_md5_match'] is False for f in files)},
            'limitations': 'Names/symbols/strings and package attribution are discovery evidence, not proof that stripped static copies are absent. RECORD and md5sums are installed metadata, not independent source authentication.'}


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
