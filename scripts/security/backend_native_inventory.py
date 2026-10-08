import ctypes
import hashlib
import json
import pathlib
import subprocess
import sys
from lxml import etree
import zlib

def output(args):
    return subprocess.check_output(args, text=True)

config_path = pathlib.Path('/opt/ffmpeg/share/config_components.h')
config = config_path.read_text()
for name in ('DVDSUB_DECODER', 'DVDSUB_PARSER', 'MPEGPS_DEMUXER'):
    assert f'#define CONFIG_{name} 0' in config, name
decoders = output(['/opt/ffmpeg/bin/ffmpeg', '-hide_banner', '-decoders'])
assert ' dvdsub ' not in decoders
assert etree.LIBXML_VERSION == (2, 15, 4)
assert not list(pathlib.Path('/usr/lib/x86_64-linux-gnu').glob('libavcodec.so*'))
cp_version = output(['cp', '--version']).splitlines()[0]
assert 'GNU coreutils' in cp_version
packages = []
for line in output(['dpkg-query', '-W', '-f=${binary:Package}\t${source:Package}\t${Version}\t${source:Version}\n']).splitlines():
    name, source, version, source_version = line.split('\t')
    packages.append(dict(name=name.split(':')[0], source=source, version=version, source_version=source_version))
assert not any(p['name'] == 'rust-coreutils' for p in packages)
b = ctypes.create_string_buffer(100)
ctypes.CDLL('libpcre2-8.so.0').pcre2_config_8(11, b)
assert b.value.startswith(b'10.49'), b.value
png = ctypes.CDLL('libpng16.so.16')
png.png_get_libpng_ver.restype = ctypes.c_char_p
png_version = png.png_get_libpng_ver(None).decode()
assert png_version == '1.6.59', png_version
files = {}
for p in [pathlib.Path('/opt/ffmpeg/bin/ffmpeg'), pathlib.Path('/opt/ffmpeg/bin/ffprobe'),
          pathlib.Path('/usr/lib/x86_64-linux-gnu/libxml2.so.16').resolve(),
          pathlib.Path('/usr/lib/x86_64-linux-gnu/libpcre2-8.so.0').resolve(),
          pathlib.Path('/usr/lib/x86_64-linux-gnu/libpng16.so.16').resolve(),
          pathlib.Path(etree.__file__), config_path]:
    files[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(dict(python=sys.version, lxml_libxml=etree.LIBXML_VERSION,
                     ffmpeg_version=output(['/opt/ffmpeg/bin/ffmpeg', '-version']).splitlines()[0],
                     pcre2_version=b.value.decode(), coreutils=cp_version,
                     libpng_version=png_version,
                     zlib_runtime=zlib.ZLIB_RUNTIME_VERSION,
                     excluded_ffmpeg_components=['dvdsub decoder', 'dvdsub parser', 'mpegps demuxer'],
                     old_ffmpeg_shared_libraries_present=False,
                     packages=packages, file_sha256=files), indent=2))
