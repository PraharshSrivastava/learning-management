"""Add reviewed native provenance to a separate copy of the raw CycloneDX SBOM.

This is inventory enrichment, not an advisory scan or a complete binary audit.
The raw Trivy SBOM stays unchanged. Only this batch's verified versions qualify.
"""
import argparse
import hashlib
import json
import uuid
from pathlib import Path

SOURCES = {
    'libxml2-16': ('2.15.4+lms1', 'https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.tar.xz', '98087fd181d9070724f3fbc65c7377db03038eb92bd882374daff44940138821'),
    'libpcre2-8-0': ('10.49+lms1', 'https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.49/pcre2-10.49.tar.gz', '929f0b20e62879252a15886b06c89f1edef61a363cbd5826fb041080a5e557ae'),
    'libpng16-16t64': ('1.6.59+lms1', 'https://deb.debian.org/debian/pool/main/libp/libpng1.6/libpng1.6_1.6.59.orig.tar.gz', '2540302a1844ad2b2b501977abecfa850f265f97b78f065a712ab4074a89f5b5'),
}
UTIL_LINUX_PACKAGES = {'lms-libmount1', 'lms-libblkid1', 'lms-libuuid1', 'lms-util-linux-security-tools'}
PARSER_SOURCES = {
    'libexpat1': ('2.8.5+lms1', 'https://deb.debian.org/debian/pool/main/e/expat/expat_2.8.5.orig.tar.gz', 'fd022c541a189bd5bee042a22188351b31e39b9389c2525fa98c28bd05c9ef21'),
    'libtiff6': ('4.7.2+lms1', 'https://deb.debian.org/debian/pool/main/t/tiff/tiff_4.7.2.orig.tar.bz2', 'c5086d8f7c5ba51ca98241f24a8bd1cb66218c399077aeccbf6a236cf3152acc'),
    'libacl1': ('2.4.0+lms1', 'https://deb.debian.org/debian/pool/main/a/acl/acl_2.4.0.orig.tar.xz', 'e661131456d2708a01c614a0f400e11d7d1bfaeb6f3e74b75bb980b72f0161a3'),
    'libx11-6': ('2:1.8.13+lms1', 'https://deb.debian.org/debian/pool/main/libx/libx11/libx11_1.8.13.orig.tar.gz', 'acf0e7cd7541110e6330ecb539441a2d53061f386ec7be6906dfde0de2598470'),
    'libx11-xcb1': ('2:1.8.13+lms1', 'https://deb.debian.org/debian/pool/main/libx/libx11/libx11_1.8.13.orig.tar.gz', 'acf0e7cd7541110e6330ecb539441a2d53061f386ec7be6906dfde0de2598470'),
    'libxrender1': ('1:0.9.12+lms1', 'https://deb.debian.org/debian/pool/main/libx/libxrender/libxrender_0.9.12.orig.tar.gz', '0fff64125819c02d1102b6236f3d7d861a07b5216d8eea336c3811d31494ecf7'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    root = args.evidence
    raw = root / 'backend.raw.cdx.json'
    bom = json.loads(raw.read_text())
    inventory = json.loads((root / 'native-inventory.json').read_text())
    assert inventory['libpng_version'] == '1.6.59'
    assert inventory['ffmpeg_version'].startswith('ffmpeg version 9.0.2 ')
    assert inventory['lxml_libxml'] == [2, 15, 4]
    matches = set()
    utility_matches = set()
    parser_matches = set()
    parser_proof = root / 'parser-smoke.json'
    medium_proof = root / 'medium-smoke.json'
    if medium_proof.exists():
        medium = json.loads(medium_proof.read_text())
        assert medium['versions']['libexpat1'] == '2.8.5+lms2'
        for name in ('libexpat1', 'libx11-6', 'libx11-xcb1'):
            _, url, digest = PARSER_SOURCES[name]
            PARSER_SOURCES[name] = (medium['versions'][name], url, digest)
        PARSER_SOURCES.update({
            'libxi6': ('2:1.8.2+lms1', 'https://deb.debian.org/debian/pool/main/libx/libxi/libxi_1.8.2.orig.tar.gz', '5542daec66febfeb6f51d57abfa915826efe2e3af57534f4105b82240ea3188d'),
            'libp11-kit0': ('0.26.5+lms1', 'https://deb.debian.org/debian/pool/main/p/p11-kit/p11-kit_0.26.5.orig.tar.xz', 'f2cc09111e44bf3fea58f023180b33acea90aa82d042d6fbb623fbc5ba033bb7'),
        })
    if parser_proof.exists():
        proof = json.loads(parser_proof.read_text())
        assert proof['xml_version'] == 'expat_2.8.5' and proof['tiff_version'] == '4.7.2'
        assert proof['acl_tar_roundtrip'] == proof['acl_nofollow'] == 'PASS'
    backlog_proof = root / 'backlog-smoke.json'
    backlog_packages = {}
    if backlog_proof.exists():
        checked = json.loads(backlog_proof.read_text())
        assert checked['dependency_check'] == checked['cups_guard_page'] == 'PASS'
        backlog_packages = {entry['package']: entry for entry in
                            checked['abi'] + checked['extra_provenance']}
    for component in bom['components']:
        name = component['name']
        if name in backlog_packages:
            entry = backlog_packages[name]
            assert component['version'] == entry['version']
            assert not entry['missing_exports']
            component.setdefault('properties', []).extend([
                {'name': 'lms:maintenance', 'value': 'Operator native backport; retained vendor files and auxiliary utilities are not claimed upgraded'},
                {'name': 'lms:reviewed-binary-sha256', 'value': entry['sha256']},
                {'name': 'lms:backlog-regression-evidence-sha256', 'value': hashlib.sha256(backlog_proof.read_bytes()).hexdigest()},
                {'name': 'lms:maintenance-recipe-sha256', 'value': hashlib.sha256((root / 'Dockerfile.backlog22').read_bytes()).hexdigest()},
            ])
        if parser_proof.exists() and name in PARSER_SOURCES:
            version, url, digest = PARSER_SOURCES[name]
            assert component['version'] == version
            parser_matches.add(name)
            component.setdefault('properties', []).extend([
                {'name': 'lms:source-archive-sha256', 'value': digest},
                {'name': 'lms:maintenance', 'value': 'Operator-built native security maintenance; ELF ABI and runtime parser/codec/ACL compatibility checked'},
            ])
            component.setdefault('externalReferences', []).append({'type': 'distribution', 'url': url})
            if medium_proof.exists() and name in ('libx11-6','libx11-xcb1','libxi6','libexpat1'):
                patch = 'libx11-medium.patch' if name.startswith('libx11') else 'libxi-medium.patch' if name == 'libxi6' else 'expat-medium.patch'
                component['properties'].append({'name':'lms:additional-upstream-patch-sha256',
                                                'value':hashlib.sha256((root/patch).read_bytes()).hexdigest()})
            if name.startswith('libx11') or name == 'libxrender1':
                advisory, patch_hash = ('CVE-2026-88806', 'e3803e8f544f767819cad13eb313129a0db4b47feeced0e17428244359b5eddd') if name.startswith('libx11') else ('CVE-2026-88807', '5ec7674c395a731dbeb7160bb65cb44f961d75e3eabcfff7b9568feb1d05e978')
                component['properties'].extend([
                    {'name': 'lms:security-patch', 'value': advisory + '; pinned upstream merge-request patch, not a new upstream release'},
                    {'name': 'lms:security-patch-sha256', 'value': patch_hash},
                ])
        if parser_proof.exists() and name in ('pillow', 'python'):
            component.setdefault('properties', []).append({'name': 'lms:parser-linkage', 'value': 'CPython pyexpat rebuilt against system Expat 2.8.5; Pillow 12.3.0 rebuilt against system TIFF 4.7.2; previous private TIFF removed'})
        if name in SOURCES:
            version, url, digest = SOURCES[name]
            assert component['version'] == version
            matches.add(name)
            component.setdefault('properties', []).extend([
                {'name': 'lms:maintenance', 'value': 'Operator-built upstream source; not an official Ubuntu binary'},
                {'name': 'lms:source-archive-sha256', 'value': digest},
            ])
            component.setdefault('externalReferences', []).append({'type': 'distribution', 'url': url})
        if name == 'lxml':
            component.setdefault('properties', []).append({'name': 'lms:libxml2-runtime', 'value': '2.15.4; source-built lxml 6.1.3, verified at runtime'})
        if name in UTIL_LINUX_PACKAGES:
            assert inventory['util_linux_security_version'] == '2.42.4'
            assert component['version'] == '2.42.4+lms1'
            utility_matches.add(name)
            component.setdefault('properties', []).extend([
                {'name': 'lms:source-archive-sha256', 'value': 'fbd62a100ab7bb8746ba0661255c3c48185b1e9021507c624da01fbc696330ec'},
                {'name': 'lms:maintenance', 'value': 'Operator-built partial util-linux replacement; only libmount/libblkid/libuuid and mount/umount/nsenter. Other utilities retain Ubuntu versions.'},
                {'name': 'lms:abi-compatibility-provider', 'value': 'Library packages provide Ubuntu 2.41.3-3ubuntu2.2 ABI for existing exact-version dependencies; actual source/code version is 2.42.4.'},
            ])
            component.setdefault('externalReferences', []).append({'type': 'distribution', 'url': 'https://www.kernel.org/pub/linux/utils/util-linux/v2.42/util-linux-2.42.4.tar.xz'})
    assert matches == set(SOURCES), matches
    if parser_proof.exists():
        assert parser_matches == set(PARSER_SOURCES), parser_matches
    if 'util_linux_security_version' in inventory:
        assert utility_matches == UTIL_LINUX_PACKAGES, utility_matches
    ref = 'pkg:generic/ffmpeg@9.0.2?lms_build=minimal-amd64'
    assert all(c.get('bom-ref') != ref for c in bom['components'])
    bom['components'].append({
        'type': 'application', 'name': 'ffmpeg', 'version': '9.0.2', 'bom-ref': ref, 'purl': ref,
        'description': 'Manually inventoried upstream source build; ffmpeg and ffprobe. Automatic Trivy package detection does not cover this installation.',
        'hashes': [{'alg': 'SHA-256', 'content': inventory['file_sha256']['/opt/ffmpeg/bin/ffmpeg']}],
        'externalReferences': [{'type': 'distribution', 'url': 'https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz'}],
        'properties': [
            {'name': 'lms:source-archive-sha256', 'value': '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e'},
            {'name': 'lms:excluded-code', 'value': '; '.join(inventory['excluded_ffmpeg_components'])},
            {'name': 'lms:maintenance', 'value': 'Operator-maintained native build; compare upstream advisories separately'},
            {'name': 'lms:ffprobe-sha256', 'value': inventory['file_sha256']['/opt/ffmpeg/bin/ffprobe']},
            {'name': 'lms:configuration-sha256', 'value': inventory['file_sha256']['/opt/ffmpeg/share/config_components.h']},
        ],
    })
    container_ref = bom['metadata']['component']['bom-ref']
    dependencies = bom.setdefault('dependencies', [])
    parent = next((d for d in dependencies if d['ref'] == container_ref), None)
    if parent is None:
        parent = {'ref': container_ref, 'dependsOn': []}
        dependencies.append(parent)
    parent.setdefault('dependsOn', []).append(ref)
    bom['serialNumber'] = 'urn:uuid:' + str(uuid.uuid4())
    bom.setdefault('properties', []).extend([
        {'name': 'lms:raw-sbom-sha256', 'value': hashlib.sha256(raw.read_bytes()).hexdigest()},
        {'name': 'lms:coverage-limit', 'value': 'Manual native enrichment only. Chrome, Python bundled native dependencies, Flutter/CanvasKit and runtime-loaded assets require additional advisory review. Zero detected matches is not complete coverage.'},
    ])
    (root / 'backend.enriched.cdx.json').write_text(json.dumps(bom, indent=2) + '\n')
    print(f'Enriched {len(bom["components"])} components; raw SBOM preserved.')


if __name__ == '__main__':
    main()
