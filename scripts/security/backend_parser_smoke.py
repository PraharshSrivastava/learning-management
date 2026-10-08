"""Exercise XML rejection, image codecs and ACL/tar compatibility offline."""
import ctypes
import hashlib
import io
import json
import pathlib
import subprocess
import tempfile
import pyexpat
import xml.etree.ElementTree as ET
from PIL import Image, features, _imaging

assert pyexpat.EXPAT_VERSION == 'expat_2.8.5', pyexpat.EXPAT_VERSION
assert features.version('libtiff') == '4.7.2', features.version('libtiff')
linkage = {}
for module in (pyexpat, _imaging):
    result = subprocess.check_output(['ldd', module.__file__], text=True)
    assert 'not found' not in result
    assert 'pillow.libs' not in result, result
    linkage[module.__name__] = result
assert 'libexpat.so.1' in linkage['pyexpat']
assert 'libtiff.so.6' in linkage['PIL._imaging']
assert not list(pathlib.Path(_imaging.__file__).parent.parent.glob('pillow.libs/*'))

# The high-surrogate sequence must be rejected by direct Expat and ElementTree,
# which uses pyexpat's capsule. A normal supplementary character remains valid.
invalid = b'\xff\xfe' + '<root>'.encode('utf-16le') + b'\x00\xd8A\x00' + '</root>'.encode('utf-16le')
for parse in (lambda b: pyexpat.ParserCreate().Parse(b, True), ET.fromstring):
    try:
        parse(invalid)
    except (pyexpat.ExpatError, ET.ParseError):
        pass
    else:
        raise AssertionError('Malformed UTF-16 surrogate accepted')
valid = '<root>\U0001f642</root>'.encode('utf-16')
pyexpat.ParserCreate().Parse(valid, True)
assert ET.fromstring(valid).text == '\U0001f642'

codec_results = {}
image = Image.new('RGB', (48, 32), (120, 80, 160))
for fmt, options in [('PNG', {}), ('JPEG', {'progressive': True}), ('WEBP', {}),
                     ('AVIF', {}), ('JPEG2000', {}), ('TIFF', {'compression': 'tiff_lzw'}),
                     ('TIFF', {'compression': 'tiff_adobe_deflate'})]:
    stream = io.BytesIO()
    image.save(stream, format=fmt, **options)
    stream.seek(0)
    with Image.open(stream) as decoded:
        decoded.load()
        assert decoded.size == image.size
    codec_results[fmt + ':' + str(options)] = 'PASS'
stream = io.BytesIO()
image.save(stream, format='TIFF', save_all=True, append_images=[image.copy()], compression='tiff_lzw')
stream.seek(0)
with Image.open(stream) as decoded:
    assert decoded.n_frames == 2
    decoded.seek(1)
    decoded.load()
    assert decoded.size == image.size
for feature in ('freetype2', 'littlecms2', 'raqm', 'webp', 'avif', 'jpg', 'jpg_2000', 'xcb', 'tkinter'):
    assert features.check(feature), feature

acl = ctypes.CDLL('libacl.so.1', use_errno=True)
acl.acl_from_text.argtypes = [ctypes.c_char_p]
acl.acl_from_text.restype = ctypes.c_void_p
acl.acl_set_file.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
acl.acl_get_file.argtypes = [ctypes.c_char_p, ctypes.c_int]
acl.acl_get_file.restype = ctypes.c_void_p
acl.acl_to_text.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
acl.acl_to_text.restype = ctypes.c_void_p
acl.acl_free.argtypes = [ctypes.c_void_p]
acl.acl_set_file_at.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
def acl_text(path):
    handle = acl.acl_get_file(str(path).encode(), 0x8000)
    assert handle, ctypes.get_errno()
    text = acl.acl_to_text(handle, None)
    assert text
    result = ctypes.string_at(text)
    acl.acl_free(text)
    acl.acl_free(handle)
    return result
with tempfile.TemporaryDirectory(prefix='lms-acl-') as directory:
    root = pathlib.Path(directory)
    source = root / 'source'
    source.mkdir()
    file = source / 'file.txt'
    file.write_text('ACL compatibility payload\n')
    handle = acl.acl_from_text(b'u::rw-,u:10002:r--,g::r--,m::r--,o::---')
    assert handle
    assert acl.acl_set_file(str(file).encode(), 0x8000, handle) == 0, ctypes.get_errno()
    acl.acl_free(handle)
    expected = acl_text(file)
    assert b'user:10002:r--' in expected
    link = root / 'symlink'
    link.symlink_to(file)
    different = acl.acl_from_text(b'u::rw-,g::---,o::---')
    assert different
    # The new no-follow API must reject the symlink and preserve target ACLs.
    assert acl.acl_set_file_at(-100, str(link).encode(), 0x100, 0x8000, different) == -1
    acl.acl_free(different)
    assert acl_text(file) == expected
    target = root / 'restored'
    target.mkdir()
    archive = root / 'test.tar'
    subprocess.run(['tar', '--acls', '-cf', str(archive), '-C', str(source), 'file.txt'], check=True)
    subprocess.run(['tar', '--acls', '-xf', str(archive), '-C', str(target)], check=True)
    assert (target / 'file.txt').read_bytes() == file.read_bytes()
    assert acl_text(target / 'file.txt') == expected
abi = json.loads(pathlib.Path('/usr/share/lms-security/native-abi-check.json').read_text())
assert len(abi) == 6 and all(not row['missing_exports'] for row in abi)
files = [pathlib.Path(pyexpat.__file__), pathlib.Path(_imaging.__file__)]
files.extend((pathlib.Path('/usr/lib/x86_64-linux-gnu') / row['soname']).resolve() for row in abi)
assert not subprocess.check_output(['dpkg', '--audit'], text=True).strip()
subprocess.run(['apt-get', '-s', 'check'], check=True, stdout=subprocess.DEVNULL)
print(json.dumps(dict(xml_version=pyexpat.EXPAT_VERSION, tiff_version=features.version('libtiff'),
                     malformed_utf16_rejected=True, valid_utf16_preserved=True,
                     codecs=codec_results, multipage_tiff='PASS', acl_tar_roundtrip='PASS', acl_nofollow='PASS',
                     pillow_features={n: features.version(n) for n in features.get_supported()},
                     shared_parser_linkage=linkage, native_abi=abi,
                     file_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}), indent=2))
