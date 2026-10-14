"""Reconcile only reviewed advisory/component pairs; preserve open bundle risks."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

PATCHES = {
    'libx11-medium.patch':'ef883cca3954c6f9e9ed5d8b5c4d9526c9b7e808037445f2b68b0df1bcbcf0b9',
    'libxi-medium.patch':'19730c2e78fe5edf782d2b01b08bfe54b5e70f2cfa7f0472c8f0e4ecc368e610',
    'expat-medium.patch':'b6684c44b8222c43166b58c14b6a439be87ab77c05cfc6eb35330ad03a697f30',
    'CVE-2025-68276-avahi.patch':'4f6bf8ce58a35098fe61d0891c009c33e5b3c9dbfba86301473ee82ed1a9d148',
    'CVE-2025-68468-avahi.patch':'9e4eabf09c86cd1f5792a8f2f4fc886dbde570b52875cfd23fa79ff62fef69c1',
    'CVE-2025-68471-avahi.patch':'aaeff91bd65047c52b07427c4e99ad540908855a73041b1c905fc5f2b90455ce',
    'alsa-topology-Makefile.am':'cd5385cea15e14cefa14038a63d2c0a6693865e4a3a00307262bd063b5b78331',
}
TARGETS = {}
for source, cves, version, note in [
    ('libx11',['94283','94284','94285'],'2:1.8.13+lms2','Pinned upstream MR310 input-method length and locale buffer bounds checks; library/XCB ABI exports preserved. Unchanged libx11-data is non-executable data.'),
    ('libxi',['93541','93542','93543','93544','93545','94281','94282'],'2:1.8.2+lms1','Pinned upstream MR23 checks XInput event/reply lengths, counts and allocation sizes. SONAME and exported symbols preserved.'),
    ('expat',['102633'],'2.8.5+lms2','Upstream commit 69edbec adds an explicit realloc overflow check with SIZE_MAX regression test. Both CPython and system callers retain shared Expat linkage. Does not close CVE-2025-66382.'),
    ('p11-kit',['13757','18938'],'0.26.5+lms1','Upstream release 0.26.5 contains both reviewed fixes. Installed shared library ABI preserved; upstream tests and GnuTLS initialization checked. No PKCS#11 token/hardware test.'),
]:
    for cve in cves:
        TARGETS[source,'CVE-2026-'+cve] = ('UPSTREAM_SECURITY_FIX_VERIFIED',version,note)
TARGETS.update({
    ('alsa-lib','CVE-2026-96674'):('AFFECTED_COMPONENT_ABSENT_VERIFIED','1.2.15.3-1ubuntu1.1 (libasound/data only)','Affected src/topology/ctl.c builds into the separate libatopology library according to the pinned upstream v1.2.15.3 Makefile. No libatopology shared/static library is shipped and libasound lacks snd_tplg_decode. Does not close ctlparse or multi-PCM advisories.'),
    **{('avahi',cve):('AFFECTED_COMPONENT_ABSENT_VERIFIED','0.8-18ubuntu1.1 (client/common only)','59529 affects avahi-daemon/simple-protocol.c; the other three fixes change avahi-core/browse.c. Neither daemon nor core library is shipped. Client/common libraries lack the affected server API. No version upgrade claimed.') for cve in ['CVE-2025-59529','CVE-2025-68276','CVE-2025-68468','CVE-2025-68471']},
    ('freetype','CVE-2026-95512'):('VENDOR_FIXED_VERSION_CONFIRMED','2.14.2+dfsg-1ubuntu0.2','Ubuntu security repository maintenance update installed; Pillow links shared FreeType and font rendering checked.'),
    ('tiff','CVE-2026-18495'):('UPSTREAM_AFFECTED_COMPONENTS_FIXED_VERIFIED','4.7.2+lms1','Existing shared TIFF 4.7.2 includes upstream fix 67fd283 (first released in 4.7.1rc1). Pillow uses the same library; codec tests passed. This is newly verified existing remediation.'),
    ('cups','CVE-2025-58436'):('UPSTREAM_AFFECTED_COMPONENTS_FIXED_VERIFIED','2.4.16-1ubuntu1.3','Existing CUPS 2.4.16 includes upstream fix 5d414f1 (2.4.15). Does not close CVE-2026-87875.'),
    ('cups','CVE-2025-61915'):('UPSTREAM_AFFECTED_COMPONENTS_FIXED_VERIFIED','2.4.16-1ubuntu1.3','Existing CUPS 2.4.16 includes upstream fix db8d560 (2.4.15). Does not close CVE-2026-87875.'),
    ('acl','CVE-2026-54370'):('AFFECTED_COMPONENT_ABSENT_VERIFIED','2.4.0+lms1 (shared library only)','Advisory concerns recursive setfacl/chacl walk_tree. Neither tool nor acl executable package is installed; only the maintained shared library is shipped. No claim that absent utilities were upgraded.'),
})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('previous',type=Path);p.add_argument('evidence',type=Path)
    a=p.parse_args(); root=a.evidence
    proof=json.loads((root/'medium-smoke.json').read_text())
    assert proof['gnutls_initialization']==proof['certificate_store']=='PASS'
    assert proof['architecture']=='x86_64' and proof['size_t_bits']==64
    assert not any(proof['absent_tools'].values()) and proof['avahi_client_has_server_api'] is False and proof['avahi_core_paths']==[]
    assert proof['alsa_topology_paths']==[] and proof['libasound_exports_snd_tplg_decode'] is False
    assert proof['xml_version']=='expat_2.8.5' and proof['tiff_version']=='4.7.2'
    for patch,digest in PATCHES.items():
        assert hashlib.sha256((root/patch).read_bytes()).hexdigest()==digest
    inv=json.loads((root/'native-inventory.json').read_text())
    versions={x['name']:x['version'] for x in inv['packages']}
    for name,version in proof['versions'].items(): assert versions[name]==version
    assert versions['libtiff6']=='4.7.2+lms1' and versions['libcups2t64']=='2.4.16-1ubuntu1.3'
    assert 'acl' not in versions and versions['libacl1']=='2.4.0+lms1'
    assert inv['zlib_runtime']=='1.3.1' and versions['zlib1g']=='1:1.3.dfsg+really1.3.1-1ubuntu3.1'
    removed=json.loads((root/'removed-components.json').read_text())
    assert removed['elf64_files_checked']>=1308 and not removed['forbidden_dynamic_dependencies']
    image=(root/'image-id.txt').read_text().strip()
    assert json.loads((root/'image-inspect.json').read_text())[0]['Id']==image
    assert 'All candidate dependency smoke checks passed.' in (root/'smoke.log').read_text()
    rows=list(csv.DictReader(a.previous.open(newline='',encoding='utf-8')))
    changes=[]
    for row in rows:
        row['prior_round4_assessment']=row['assessment']
        if not row['assessment'].startswith('OPEN_'):continue
        key=row['source'],row['advisory']
        if key in TARGETS:
            assert row['severity']=='MEDIUM'
            status,version,note=TARGETS[key]
            row.update(assessment=status,candidate_source_versions=version,notes=note,
                       evidence_url='https://security-tracker.debian.org/tracker/'+row['advisory'])
        elif key==('cjson','CVE-2026-16554'):
            assert row['severity']=='HIGH'
            row.update(assessment='UPSTREAM_NOT_AFFECTED_ARCHITECTURE_VERIFIED',
                       notes='CERT Polska identifies this size_t overflow as 32-bit only. Candidate is amd64; all 1308 inventoried ELF files are 64-bit and Python size_t is 64-bit. Other cJSON advisories and unidentified static copy provenance remain open.',
                       evidence_url='https://cert.pl/en/posts/2026/07/CVE-2026-16554/')
        else:continue
        changes.append({k:row[k] for k in ('source','package','advisory','severity','assessment')})
    assert len(changes)==39 and Counter(x['severity'] for x in changes)=={'MEDIUM':38,'HIGH':1}, Counter(x['severity'] for x in changes)
    with (root/'inherited-reconciled.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(candidate_image=image,inherited_occurrences=len(rows),changes=changes,
                 open_original_severity=dict(Counter(r['severity'] for r in rows if r['assessment'].startswith('OPEN_'))),
                 assessments=dict(Counter(r['assessment'] for r in rows)),
                 previous_register_sha256=hashlib.sha256(a.previous.read_bytes()).hexdigest(),
                 limitations='Six High bundle/source reviews remain open despite OS library removal and zero detected High matches. Counts are inherited package-advisory occurrences, not unique CVEs. No suppression or deployment.')
    (root/'inherited-reconciled.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary['open_original_severity']))
if __name__=='__main__':main()
