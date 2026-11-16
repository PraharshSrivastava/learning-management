"""Verify the consolidated maintenance versions and their runtime linkage."""
import ctypes
import hashlib
import json
from pathlib import Path
import ssl
import platform
import subprocess
import shutil
import pyexpat
from PIL import features

expected = {'libx11-6':'2:1.8.13+lms2', 'libx11-xcb1':'2:1.8.13+lms2',
            'libxi6':'2:1.8.2+lms1', 'libexpat1':'2.8.5+lms2',
            'libfreetype6':'2.14.2+dfsg-1ubuntu0.2', 'libp11-kit0':'0.26.5+lms1'}
assert platform.machine() == 'x86_64' and ctypes.sizeof(ctypes.c_size_t) == 8
versions = {}
for package, version in expected.items():
    value = subprocess.check_output(['dpkg-query','-W','-f=${Version}',package],text=True)
    assert value == version, (package,value)
    versions[package] = value
proofs = {}
for name in ['xclient-abi-check','expat-medium-abi-check','p11-medium-abi-check']:
    rows = json.loads((Path('/usr/share/lms-security')/(name+'.json')).read_text())
    assert rows and all(not r['missing_exports'] for r in rows)
    proofs[name] = rows
    for row in rows:
        assert row['version'] == expected[row['package']]
        ctypes.CDLL(row['soname'])
gnutls = ctypes.CDLL('libgnutls.so.30')
assert gnutls.gnutls_global_init() == 0
gnutls.gnutls_global_deinit()
assert ssl.create_default_context().cert_store_stats()['x509_ca'] > 0
assert pyexpat.EXPAT_VERSION == 'expat_2.8.5'
assert features.version('libtiff') == '4.7.2'
assert features.check('freetype2')
assert not subprocess.check_output(['dpkg','--audit'],text=True).strip()
absent_tools = {name: shutil.which(name) for name in ['avahi-daemon','setfacl','chacl']}
assert not any(absent_tools.values()), absent_tools
avahi_core_paths = list(Path('/usr/lib').rglob('libavahi-core.so*'))
assert not avahi_core_paths, avahi_core_paths
avahi_client = ctypes.CDLL('libavahi-client.so.3')
for symbol in ['avahi_server_new','avahi_s_record_browser_prepare','avahi_s_record_browser_new']:
    assert not hasattr(avahi_client,symbol), symbol
alsa_topology_paths = list(Path('/usr/lib').rglob('libatopology*'))
assert not alsa_topology_paths, alsa_topology_paths
assert not hasattr(ctypes.CDLL('libasound.so.2'),'snd_tplg_decode')
subprocess.run(['apt-get','-s','check'],check=True,stdout=subprocess.DEVNULL)
libraries = ['libX11.so.6','libX11-xcb.so.1','libXi.so.6','libexpat.so.1','libfreetype.so.6','libp11-kit.so.0']
paths = [(Path('/usr/lib/x86_64-linux-gnu')/p).resolve() for p in libraries]
p11_bytes = (Path('/usr/lib/x86_64-linux-gnu')/'libp11-kit.so.0').read_bytes()
assert b'/usr/etc/pkcs11' not in p11_bytes
assert all(x in p11_bytes for x in [b'/etc/pkcs11',b'/usr/share/p11-kit/modules',b'/usr/lib/x86_64-linux-gnu/pkcs11'])
print(json.dumps(dict(versions=versions,abi=proofs,gnutls_initialization='PASS',
                      architecture=platform.machine(),size_t_bits=ctypes.sizeof(ctypes.c_size_t)*8,
                      absent_tools=absent_tools,avahi_core_paths=[],avahi_client_has_server_api=False,
                      alsa_topology_paths=[],libasound_exports_snd_tplg_decode=False,
                      p11_configuration_paths='Ubuntu paths preserved',
                      certificate_store='PASS',xml_version=pyexpat.EXPAT_VERSION,
                      tiff_version=features.version('libtiff'),freetype_version=features.version('freetype2'),
                      shared_library_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2))
