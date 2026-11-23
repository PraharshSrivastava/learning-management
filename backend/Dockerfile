FROM python:3.12.14-slim-trixie@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f AS python-runtime
FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS ffmpeg-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gcc g++ make pkg-config nasm xz-utils libx264-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# This hash was independently verified against the upstream release signature.
RUN curl --fail --location --retry 2 -o ffmpeg.tar.xz https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz \
    && echo '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e  ffmpeg.tar.xz' | sha256sum -c - \
    && tar -xf ffmpeg.tar.xz \
    && cd ffmpeg-9.0.2 \
    && ./configure --prefix=/opt/ffmpeg --disable-debug --disable-doc --disable-ffplay \
        --disable-autodetect --disable-everything --enable-gpl --enable-libx264 --enable-zlib \
        --enable-ffmpeg --enable-ffprobe --enable-protocol=file,pipe \
        --enable-bsf=aac_adtstoasc,h264_mp4toannexb,extract_extradata,null \
        --enable-decoder=wrapped_avframe,png,mjpeg,h264,aac,mp3,mp3float,flac,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,pcm_f64le,pcm_u8 \
        --enable-encoder=libx264,aac,pcm_s16le,png,mjpeg \
        --enable-parser=h264,aac,mpegaudio,flac \
        --enable-demuxer=image2,image2pipe,wav,mp3,mov,concat,aac,flac \
        --enable-muxer=mp4,mov,hls,wav,adts,null,mpegts \
        --enable-filter=buffer,buffersink,abuffer,abuffersink,color,format,aformat,scale,aresample,apad,atempo,anull,null,split,asplit,trim,atrim \
        --disable-network --disable-indevs --disable-outdevs --enable-indev=lavfi \
        --extra-cflags='-fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIE' \
        --extra-ldflags='-Wl,-z,relro,-z,now -pie' \
    && make -j2 \
    && make install \
    && ! nm libavcodec/libavcodec.a | grep -E 'ff_dvdsub_(decoder|parser)' \
    && install -Dm644 COPYING.GPLv2 /opt/ffmpeg/share/licenses/FFmpeg/COPYING.GPLv2 \
    && cp config.h config_components.h ffbuild/config.mak /opt/ffmpeg/share/ \
    && /opt/ffmpeg/bin/ffmpeg -version \
    && /opt/ffmpeg/bin/ffprobe -version
FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS xml-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gcc make pkg-config xz-utils zlib1g-dev libxml2-16 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl --fail --location --retry 2 -o libxml2.tar.xz https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.tar.xz \
    && echo '98087fd181d9070724f3fbc65c7377db03038eb92bd882374daff44940138821  libxml2.tar.xz' | sha256sum -c - \
    && tar -xf libxml2.tar.xz \
    && cd libxml2-2.15.4 \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --without-python --with-zlib --with-legacy --with-http \
        CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIC' LDFLAGS='-Wl,-z,relro,-z,now' \
    && make -j2 \
    && make check \
    && make DESTDIR=/install install \
    && mkdir -p /package/DEBIAN /package/usr/lib/x86_64-linux-gnu /package/usr/share/doc/libxml2-16 /out \
    && cp -a /install/usr/lib/x86_64-linux-gnu/libxml2.so.16* /package/usr/lib/x86_64-linux-gnu/ \
    && cp Copyright /package/usr/share/doc/libxml2-16/copyright \
    && printf 'Package: libxml2-16\nSource: libxml2\nVersion: 2.15.4+lms1\nArchitecture: amd64\nMaintainer: LMS security maintainer\nSection: libs\nPriority: optional\nDepends: libc6 (>= 2.38), zlib1g (>= 1:1.2.2.3)\nDescription: GNOME XML library, verified upstream security maintenance build\n' > /package/DEBIAN/control \
    && nm -D --defined-only /usr/lib/x86_64-linux-gnu/libxml2.so.16 | awk '{print $3}' | sort > /out/old-symbols.txt \
    && nm -D --defined-only /package/usr/lib/x86_64-linux-gnu/libxml2.so.16 | awk '{print $3}' | sort > /out/new-symbols.txt \
    && comm -23 /out/old-symbols.txt /out/new-symbols.txt > /out/missing-symbols.txt \
    && cat /out/missing-symbols.txt \
    && test ! -s /out/missing-symbols.txt \
    && dpkg-deb --build --root-owner-group /package /out/libxml2-16_2.15.4+lms1_amd64.deb \
    && ./xmllint --version \
    && cp config.log /out/config.log
FROM xml-build AS lxml-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends libxslt1-dev libssl3t64 libffi8 libexpat1 libbz2-1.0 liblzma5 zlib1g ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-runtime /usr/local/ /usr/local/
COPY --from=xml-build /install/usr/ /usr/
RUN ldconfig
COPY requirements-lxml-source.lock /src/requirements-lxml-source.lock
RUN python -m pip wheel --no-deps --no-binary=lxml --require-hashes -r /src/requirements-lxml-source.lock --wheel-dir=/out/wheels \
    && cd /out/wheels && sha256sum lxml-*.whl > SHA256SUMS

COPY security/record_source_wheel.py /src/
RUN python /src/record_source_wheel.py --source-lock /src/requirements-lxml-source.lock --wheels /out/wheels --output /out/lxml-source-build.json \
        --config-tool xml2-config --config-tool xslt-config

FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS app-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    IMAGEIO_FFMPEG_EXE=/opt/ffmpeg/bin/ffmpeg

ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

# Install runtime libraries from one supported distribution; do not copy Debian OS libraries.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        ca-certificates tzdata libx264-165 libxslt1.1 libreoffice-writer libreoffice-impress fonts-dejavu-core \
        libbz2-1.0 libffi8 liblzma5 libreadline8t64 libsqlite3-0 libssl3t64 \
        zlib1g libexpat1 libuuid1 libgdbm6t64 libgdbm-compat4t64 libncursesw6 openssl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-runtime /usr/local/ /usr/local/
ENV PATH="/opt/ffmpeg/bin:/usr/local/bin:${PATH}"
RUN ldconfig \
    && python -c "import ssl,sqlite3,bz2,lzma,ctypes,readline,dbm.gnu,dbm.ndbm,uuid,pyexpat; print(ssl.OPENSSL_VERSION); print(sqlite3.sqlite_version)"
COPY --from=xml-build /out/libxml2-16_2.15.4+lms1_amd64.deb /tmp/libxml2.deb
RUN dpkg -i /tmp/libxml2.deb && ldconfig && rm /tmp/libxml2.deb
COPY --from=ffmpeg-build /opt/ffmpeg/ /opt/ffmpeg/
COPY --from=lxml-build /out/wheels/ /tmp/lxml-wheels/
COPY requirements-bootstrap.lock ./
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --require-hashes --only-binary=:all: -r requirements-bootstrap.lock

COPY requirements.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --require-hashes -r requirements.lock \
    && (cd /tmp/lxml-wheels && sha256sum -c SHA256SUMS) \
    && python -m pip install --no-cache-dir --no-index --no-deps --force-reinstall /tmp/lxml-wheels/lxml-*.whl \
    && rm -rf /tmp/lxml-wheels \
    && python -m playwright install --with-deps chromium

# Validate the installed dependency set, then remove build-only pip and its vendored libraries.
# Use the verified upstream FFmpeg build; remove the older wheel-bundled executable.
RUN python -m pip check \
    && python -c "from pathlib import Path; import imageio_ffmpeg; bins = Path(imageio_ffmpeg.__file__).parent / 'binaries'; [p.unlink() for p in bins.glob('ffmpeg-*') if p.is_file()]; assert imageio_ffmpeg.get_ffmpeg_exe() == '/opt/ffmpeg/bin/ffmpeg'" \
    && python -m pip uninstall --yes pip

COPY app ./app
COPY scripts ./scripts

# Retain working Tcl/Tk dependencies for the copied CPython standard-library extension.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libtcl8.6 libtk8.6 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/storage \
    && chown -R app:app /app /ms-playwright

EXPOSE 8000

USER 10001:10001



HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS pcre-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gcc libc6-dev make pkg-config libpcre2-8-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# SHA-256 published in the official GitHub release asset metadata.
RUN curl --fail --location --retry 2 -o pcre2.tar.gz https://github.com/PCRE2Project/pcre2/releases/download/pcre2-10.49/pcre2-10.49.tar.gz \
    && echo '929f0b20e62879252a15886b06c89f1edef61a363cbd5826fb041080a5e557ae  pcre2.tar.gz' | sha256sum -c - \
    && tar -xf pcre2.tar.gz \
    && cd pcre2-10.49 \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --enable-jit --disable-static \
        CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIC' LDFLAGS='-Wl,-z,relro,-z,now' \
    && make -j2 \
    && make check \
    && make DESTDIR=/install install \
    && mkdir -p /package/DEBIAN /package/usr/lib/x86_64-linux-gnu /package/usr/share/doc/libpcre2-8-0 /out \
    && cp -a /install/usr/lib/x86_64-linux-gnu/libpcre2-8.so.0* /package/usr/lib/x86_64-linux-gnu/ \
    && cp LICENCE.md /package/usr/share/doc/libpcre2-8-0/copyright \
    && printf 'Package: libpcre2-8-0\nSource: pcre2\nVersion: 10.49+lms1\nArchitecture: amd64\nMaintainer: LMS security maintainer\nSection: libs\nPriority: optional\nDepends: libc6 (>= 2.38)\nDescription: PCRE2 verified upstream security maintenance build\n' > /package/DEBIAN/control \
    && nm -D --defined-only /usr/lib/x86_64-linux-gnu/libpcre2-8.so.0 | awk '{print $3}' | sort > /out/old-symbols.txt \
    && nm -D --defined-only /package/usr/lib/x86_64-linux-gnu/libpcre2-8.so.0 > /out/new-symbols-raw.txt \
    && awk '{sub(/@@.*/, "", $3); print $3}' /out/new-symbols-raw.txt | sort > /out/new-symbols.txt \
    && comm -23 /out/old-symbols.txt /out/new-symbols.txt > /out/missing-symbols.txt \
    && cat /out/missing-symbols.txt \
    && test ! -s /out/missing-symbols.txt \
    && dpkg-deb --build --root-owner-group /package /out/libpcre2-8-0_10.49+lms1_amd64.deb

FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS png-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gcc libc6-dev make zlib1g-dev libpng16-16t64 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# Upstream original archive; hash published in Debian's signed source descriptor.
RUN curl --fail --location --retry 2 -o libpng.tar.gz https://deb.debian.org/debian/pool/main/libp/libpng1.6/libpng1.6_1.6.59.orig.tar.gz \
    && echo '2540302a1844ad2b2b501977abecfa850f265f97b78f065a712ab4074a89f5b5  libpng.tar.gz' | sha256sum -c - \
    && tar -xf libpng.tar.gz \
    && cd libpng-1.6.59 \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu \
        CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIC' LDFLAGS='-Wl,-z,relro,-z,now' \
    && make -j2 \
    && make check \
    && make DESTDIR=/install install
RUN cd libpng-1.6.59 \
    && mkdir -p /package/DEBIAN /package/usr/lib/x86_64-linux-gnu /package/usr/share/doc/libpng16-16t64 /out \
    && cp -a /install/usr/lib/x86_64-linux-gnu/libpng16.so.16* /package/usr/lib/x86_64-linux-gnu/ \
    && cp LICENSE /package/usr/share/doc/libpng16-16t64/copyright \
    && printf 'Package: libpng16-16t64\nSource: libpng1.6\nVersion: 1.6.59+lms1\nArchitecture: amd64\nMaintainer: LMS security maintainer\nSection: libs\nPriority: optional\nDepends: libc6 (>= 2.38), zlib1g (>= 1:1.2.2.3)\nDescription: libpng verified upstream security maintenance build\n' > /package/DEBIAN/control \
    && nm -D --defined-only /usr/lib/x86_64-linux-gnu/libpng16.so.16 | awk '{print $3}' | sort > /out/old-symbols.txt \
    && nm -D --defined-only /package/usr/lib/x86_64-linux-gnu/libpng16.so.16 | awk '{print $3}' | sort > /out/new-symbols.txt \
    && comm -23 /out/old-symbols.txt /out/new-symbols.txt > /out/missing-symbols.txt \
    && cat /out/missing-symbols.txt \
    && test ! -s /out/missing-symbols.txt \
    && dpkg-deb --build --root-owner-group /package /out/libpng16-16t64_1.6.59+lms1_amd64.deb

FROM app-runtime AS final-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=pcre-build /out/libpcre2-8-0_10.49+lms1_amd64.deb /tmp/libpcre2.deb
COPY --from=png-build /out/libpng16-16t64_1.6.59+lms1_amd64.deb /tmp/libpng.deb
# Ubuntu's documented GNU replacement preserves the standard utilities while
# removing the unnecessary Rust implementation and its advisory exposure.
RUN dpkg -i /tmp/libpcre2.deb /tmp/libpng.deb \
    && ldconfig \
    && rm /tmp/libpcre2.deb /tmp/libpng.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends --allow-remove-essential coreutils-from-gnu coreutils-from-uutils- rust-coreutils- \
    && rm -rf /var/lib/apt/lists/* \
    && cp --version \
    && python -c "import ctypes; b=ctypes.create_string_buffer(100); ctypes.CDLL('libpcre2-8.so.0').pcre2_config_8(11,b); assert b.value.startswith(b'10.49'), b.value; png=ctypes.CDLL('libpng16.so.16'); png.png_get_libpng_ver.restype=ctypes.c_char_p; assert png.png_get_libpng_ver(None)==b'1.6.59'"
USER 10001:10001

# Only the affected utility components are replaced; other Ubuntu util-linux
# programs retain their original ownership and versions in the SBOM.
FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS util-linux-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gcc libc6-dev make pkg-config xz-utils python3 \
        libselinux1-dev libmount-dev libblkid-dev uuid-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# SHA-256 published in kernel.org's signed release checksum manifest.
RUN curl --fail --location --retry 2 -o util-linux.tar.xz https://www.kernel.org/pub/linux/utils/util-linux/v2.42/util-linux-2.42.4.tar.xz \
    && echo 'fbd62a100ab7bb8746ba0661255c3c48185b1e9021507c624da01fbc696330ec  util-linux.tar.xz' | sha256sum -c - \
    && tar -xf util-linux.tar.xz \
    && cd util-linux-2.42.4 \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --enable-static --disable-nls \
        --disable-all-programs --enable-libmount --enable-libblkid --enable-libuuid --enable-mount --enable-nsenter \
        --disable-makeinstall-chown --disable-makeinstall-setuid \
        CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIC' LDFLAGS='-Wl,-z,relro,-z,now' \
    && make -j2 \
    && make check \
    && make DESTDIR=/install install
RUN useradd --uid 10002 --create-home test-builder \
    && chown -R test-builder:test-builder /src/util-linux-2.42.4 \
    && su -s /bin/sh test-builder -c 'cd /src/util-linux-2.42.4 && ./tests/run.sh --nonroot --parallel=2 libmount'
COPY security/package_util_linux.py /src/package_util_linux.py
RUN python3 /src/package_util_linux.py

FROM final-runtime AS security-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=util-linux-build /out/*.deb /tmp/util-linux-security/
RUN apt-get install -y --no-install-recommends /tmp/util-linux-security/*.deb \
    && ldconfig \
    && rm -rf /tmp/util-linux-security \
    && apt-get purge -y xvfb xserver-common \
    && apt-get check \
    && mount --version && nsenter --version
USER 10001:10001

# Parser and X client maintenance: one shared TIFF/Expat implementation for the
# OS and Python callers. Upstream X patches are pinned separately from releases.
FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS native-parsers-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gcc g++ libc6-dev make pkg-config xz-utils bzip2 patch python3 autoconf automake libtool gettext \
        libexpat1-dev libtiff-dev libacl1-dev libattr1-dev libjpeg-dev liblzma-dev libzstd-dev libwebp-dev libjbig-dev libdeflate-dev \
        zlib1g-dev libx11-dev libxrender-dev libxcb1-dev xorg-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
ENV CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIC' \
    LDFLAGS='-Wl,-z,relro,-z,now'
RUN curl --fail --location --retry 2 -o expat.tar.gz https://github.com/libexpat/libexpat/archive/refs/tags/R_2_8_5.tar.gz \
    && echo 'fd022c541a189bd5bee042a22188351b31e39b9389c2525fa98c28bd05c9ef21  expat.tar.gz' | sha256sum -c - \
    && tar -xf expat.tar.gz && mv libexpat-R_2_8_5 expat-2.8.5 && cd expat-2.8.5/expat \
    && autoreconf -fi \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static \
    && make -j2 && make check && make DESTDIR=/native-install install
RUN curl --fail --location --retry 2 -o tiff.tar.bz2 https://deb.debian.org/debian/pool/main/t/tiff/tiff_4.7.2.orig.tar.bz2 \
    && echo 'c5086d8f7c5ba51ca98241f24a8bd1cb66218c399077aeccbf6a236cf3152acc  tiff.tar.bz2' | sha256sum -c - \
    && tar -xf tiff.tar.bz2 && mv libtiff-v4.7.2 tiff-4.7.2 && cd tiff-4.7.2 \
    && autoreconf -fi \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static --disable-tools --disable-contrib --disable-docs \
    && make -j2 && make check && make DESTDIR=/native-install install
# ACL test fixtures require GNU ls; root device/NFS groups need privileges or mounts absent in this builder.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --allow-remove-essential coreutils-from-gnu coreutils-from-uutils- rust-coreutils- attr \
    && rm -rf /var/lib/apt/lists/* \
    && curl --fail --location --retry 2 -o acl.tar.xz https://deb.debian.org/debian/pool/main/a/acl/acl_2.4.0.orig.tar.xz \
    && echo 'e661131456d2708a01c614a0f400e11d7d1bfaeb6f3e74b75bb980b72f0161a3  acl.tar.xz' | sha256sum -c - \
    && tar -xf acl.tar.xz && cd acl-2.4.0 \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static \
    && make -j2 && (make check TESTS="$(find test -maxdepth 1 -name '*.run' -printf '%p ')" || { cat test-suite.log; exit 1; }) && make DESTDIR=/native-install install
COPY security/libx11-CVE-2026-88806.patch security/libxrender-CVE-2026-88807.patch /src/
RUN echo 'e3803e8f544f767819cad13eb313129a0db4b47feeced0e17428244359b5eddd  libx11-CVE-2026-88806.patch' | sha256sum -c - \
    && echo '5ec7674c395a731dbeb7160bb65cb44f961d75e3eabcfff7b9568feb1d05e978  libxrender-CVE-2026-88807.patch' | sha256sum -c - \
    && curl --fail --location --retry 2 -o x11.tar.gz https://deb.debian.org/debian/pool/main/libx/libx11/libx11_1.8.13.orig.tar.gz \
    && echo 'acf0e7cd7541110e6330ecb539441a2d53061f386ec7be6906dfde0de2598470  x11.tar.gz' | sha256sum -c - \
    && tar -xf x11.tar.gz && cd libX11-1.8.13 \
    && patch --fuzz=0 -p1 < /src/libx11-CVE-2026-88806.patch \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static --disable-specs \
    && make -j2 && make check && make DESTDIR=/native-install install
RUN curl --fail --location --retry 2 -o xrender.tar.gz https://deb.debian.org/debian/pool/main/libx/libxrender/libxrender_0.9.12.orig.tar.gz \
    && echo '0fff64125819c02d1102b6236f3d7d861a07b5216d8eea336c3811d31494ecf7  xrender.tar.gz' | sha256sum -c - \
    && tar -xf xrender.tar.gz && cd libXrender-0.9.12 \
    && patch --fuzz=0 -p1 < /src/libxrender-CVE-2026-88807.patch \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static \
    && make -j2 && make check && make DESTDIR=/native-install install
COPY security/package_native_parsers.py /src/
RUN python3 /src/package_native_parsers.py

FROM native-parsers-build AS python-parsers-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && apt-get install -y --no-install-recommends libssl3t64 libffi8 libbz2-1.0 libsqlite3-0 libfreetype-dev liblcms2-dev libopenjp2-7-dev \
        libraqm-dev libharfbuzz-dev libfribidi-dev libavif-dev tk-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-runtime /usr/local/ /usr/local/
COPY --from=native-parsers-build /native-install/usr/ /usr/
# The compiler flags must split into separate words.
# hadolint ignore=SC2046
RUN ldconfig \
    && curl --fail --location --retry 2 -o Python.tar.xz https://www.python.org/ftp/python/3.12.14/Python-3.12.14.tar.xz \
    && echo '5c8462af5790baf43a321a1559dbe0db06d1be4300fb85fb53c40060668e548a  Python.tar.xz' | sha256sum -c - \
    && tar -xf Python.tar.xz \
    && gcc -shared -fPIC -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -Wl,-z,relro,-z,now \
        $(python3-config --includes) -I/usr/local/include/python3.12/internal -I/src/expat-2.8.5/expat \
        Python-3.12.14/Modules/pyexpat.c -lexpat -o /out/pyexpat$(python3-config --extension-suffix) \
    && PYTHONPATH=/out python -c "import pyexpat; assert pyexpat.EXPAT_VERSION=='expat_2.8.5', pyexpat.EXPAT_VERSION"
COPY requirements-pillow-source.lock /src/
RUN python -m pip wheel --no-deps --no-binary=pillow --require-hashes -r /src/requirements-pillow-source.lock --wheel-dir=/out/wheels \
    && cd /out/wheels && sha256sum pillow-*.whl > SHA256SUMS
COPY security/record_source_wheel.py /src/
RUN python /src/record_source_wheel.py --source-lock /src/requirements-pillow-source.lock --wheels /out/wheels --output /out/pillow-source-build.json

FROM security-runtime AS maintained-parsers-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=native-parsers-build /out/*.deb /tmp/native-security/
COPY --from=native-parsers-build /out/abi-check.json /usr/share/lms-security/native-abi-check.json
COPY --from=python-parsers-build /out/pyexpat*.so /usr/local/lib/python3.12/lib-dynload/
COPY --from=python-parsers-build /out/wheels/ /tmp/pillow-wheels/
# Pip remains build-only and is removed after replacing the wheel and checking
# dependencies. Reinstalling Pillow removes its previous private TIFF library.
RUN apt-get update \
    && apt-get install -y --no-install-recommends /tmp/native-security/*.deb libavif16 libjpeg-turbo8 libopenjp2-7 libwebpmux3 libwebpdemux2 libraqm0 liblcms2-2 \
    && ldconfig \
    && python -m ensurepip \
    && (cd /tmp/pillow-wheels && sha256sum -c SHA256SUMS) \
    && python -m pip install --no-cache-dir --no-index --no-deps --force-reinstall /tmp/pillow-wheels/pillow-*.whl \
    && python -m pip check \
    && python -m pip uninstall --yes pip setuptools \
    && rm -rf /tmp/native-security /tmp/pillow-wheels /var/lib/apt/lists/* \
    && apt-get -s check \
    && python -c "import pyexpat; from PIL import features; assert pyexpat.EXPAT_VERSION=='expat_2.8.5'; assert features.version('libtiff')=='4.7.2'; assert features.check('webp') and features.check('jpg') and features.check('jpg_2000') and features.check('freetype2')"
USER 10001:10001

# Batch the X client bounds checks without rebuilding unrelated parser sources.
FROM native-parsers-build AS xclient-medium-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY security/libx11-medium.patch security/libxi-medium.patch /src/
RUN echo 'ef883cca3954c6f9e9ed5d8b5c4d9526c9b7e808037445f2b68b0df1bcbcf0b9  /src/libx11-medium.patch' | sha256sum -c - \
    && echo '19730c2e78fe5edf782d2b01b08bfe54b5e70f2cfa7f0472c8f0e4ecc368e610  /src/libxi-medium.patch' | sha256sum -c - \
    && cd /src/libX11-1.8.13 \
    && patch --fuzz=0 -p1 < /src/libx11-medium.patch \
    && make -j2 && make check && make DESTDIR=/medium-install install
RUN curl --fail --location --retry 2 -o /src/xi.tar.gz https://deb.debian.org/debian/pool/main/libx/libxi/libxi_1.8.2.orig.tar.gz \
    && echo '5542daec66febfeb6f51d57abfa915826efe2e3af57534f4105b82240ea3188d  /src/xi.tar.gz' | sha256sum -c - \
    && cd /src && tar -xf xi.tar.gz && cd libXi-1.8.2 \
    && patch --fuzz=0 -p1 < /src/libxi-medium.patch \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static --disable-specs \
    && make -j2 && make check && make DESTDIR=/medium-install install
COPY security/package_xclients.py /src/
RUN python3 /src/package_xclients.py

FROM maintained-parsers-runtime AS medium-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=xclient-medium-build /medium-out/*.deb /tmp/xclient-security/
COPY --from=xclient-medium-build /medium-out/abi-check.json /usr/share/lms-security/xclient-abi-check.json
COPY security/check_removed_components.py /usr/share/lms-security/check_removed_components.py
RUN apt-get update \
    && apt-get install -y --no-install-recommends /tmp/xclient-security/*.deb libfreetype6=2.14.2+dfsg-1ubuntu0.2 \
    && ldconfig && apt-get check \
    && test -z "$(dpkg --audit)" \
    && rm -rf /tmp/xclient-security /var/lib/apt/lists/* \
    && python /usr/share/lms-security/check_removed_components.py > /usr/share/lms-security/removed-components.json
USER 10001:10001
# Preserve shared Expat/Python linkage; backport the upstream release-build
# overflow check together with its SIZE_MAX allocation regression test.
FROM native-parsers-build AS expat-medium-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY security/expat-medium.patch /src/
RUN echo 'b6684c44b8222c43166b58c14b6a439be87ab77c05cfc6eb35330ad03a697f30  /src/expat-medium.patch' | sha256sum -c - \
    && cd /src/expat-2.8.5 && patch --fuzz=0 -p1 < /src/expat-medium.patch \
    && cd expat && make -j2 && make check && make DESTDIR=/medium-install install
COPY security/package_xclients.py /src/
RUN LMS_NATIVE_BATCH=expat python3 /src/package_xclients.py

FROM medium-runtime AS medium-parsers-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=expat-medium-build /medium-out/libexpat1.deb /tmp/expat-security.deb
COPY --from=expat-medium-build /medium-out/abi-check.json /usr/share/lms-security/expat-medium-abi-check.json
RUN dpkg -i /tmp/expat-security.deb && ldconfig && apt-get check \
    && test -z "$(dpkg --audit)" && rm /tmp/expat-security.deb \
    && python -c "import pyexpat; assert pyexpat.EXPAT_VERSION == 'expat_2.8.5'"
USER 10001:10001
FROM native-parsers-build AS p11-medium-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends libffi-dev libtasn1-6-dev \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 2 -o /src/p11-kit.tar.xz https://deb.debian.org/debian/pool/main/p/p11-kit/p11-kit_0.26.5.orig.tar.xz \
    && echo 'f2cc09111e44bf3fea58f023180b33acea90aa82d042d6fbb623fbc5ba033bb7  /src/p11-kit.tar.xz' | sha256sum -c - \
    && cd /src && tar -xf p11-kit.tar.xz && cd p11-kit-0.26.5 \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static --disable-doc --disable-systemd \
    && make -j2 && make check && make DESTDIR=/medium-install install
COPY security/package_xclients.py /src/
RUN LMS_NATIVE_BATCH=p11-kit python3 /src/package_xclients.py

FROM medium-parsers-runtime AS medium-trust-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=p11-medium-build /medium-out/libp11-kit0.deb /tmp/p11-security.deb
COPY --from=p11-medium-build /medium-out/abi-check.json /usr/share/lms-security/p11-medium-abi-check.json
RUN dpkg -i /tmp/p11-security.deb && ldconfig && apt-get check \
    && test -z "$(dpkg --audit)" && rm /tmp/p11-security.deb
USER 10001:10001
# Match Ubuntu's PKCS#11 paths as well as its shared-library ABI. Reconfigure
# the cached source and rebuild the object containing these compiled defaults.
FROM p11-medium-build AS p11-config-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN cd /src/p11-kit-0.26.5 \
    && ./configure --prefix=/usr --sysconfdir=/etc --libdir=/usr/lib/x86_64-linux-gnu --disable-static --disable-doc --without-systemd \
        --with-system-config=/etc/pkcs11 --with-module-config=/usr/share/p11-kit/modules --with-module-path=/usr/lib/x86_64-linux-gnu/pkcs11 \
    && touch p11-kit/modules.c && make -j2 libp11-kit.la && make check \
    && cp -a .libs/libp11-kit.so.0* /medium-install/usr/lib/x86_64-linux-gnu/ \
    && rm -rf /medium-packages/libp11-kit0 \
    && LMS_NATIVE_BATCH=p11-kit python3 /src/package_xclients.py

FROM medium-trust-runtime AS maintained-medium-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=p11-config-build /medium-out/libp11-kit0.deb /tmp/p11-security.deb
RUN dpkg -i /tmp/p11-security.deb && ldconfig && apt-get check \
    && test -z "$(dpkg --audit)" && rm /tmp/p11-security.deb \
    && python -c "from pathlib import Path; b=Path('/usr/lib/x86_64-linux-gnu/libp11-kit.so.0').read_bytes(); assert b'/usr/etc/pkcs11' not in b; assert b'/etc/pkcs11' in b and b'/usr/share/p11-kit/modules' in b"
USER 10001:10001
# Retain document/audio interfaces while fixing native parsing at source.
FROM ubuntu:26.04@sha256:d66b366dac61b575bee2aef07e9c26e8070096fbe84a3d4d3eb0da069b5d76db AS backlog-native-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3 curl ca-certificates patch pkg-config bzip2 autoconf automake libtool quilt libasound2t64 libcups2t64 \
    libgnutls28-dev libavahi-client-dev libkrb5-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY security/alsa-ctlparse.patch security/alsa-sparse-bindings.patch security/cups-utf32.patch /src/
RUN echo 'fc88545f165594e9e7119b3c934562fcc71a7c8b2f4c78999e85662e669d02af  alsa-ctlparse.patch' | sha256sum -c - \
    && echo '6f86774595e6ebf2594cab1949bbb9ae66dd90383fb6dffa9f757bd884b6ad7e  alsa-sparse-bindings.patch' | sha256sum -c - \
    && echo '47eb967434d2dadd11c149245109f267a0016381b6edca4829355b8002f30688  cups-utf32.patch' | sha256sum -c -
RUN curl --fail --location --retry 2 -o alsa.tar.bz2 https://www.alsa-project.org/files/pub/lib/alsa-lib-1.2.15.3.tar.bz2 \
    && echo '7b079d614d582cade7ab8db2364e65271d0877a37df8757ac4ac0c8970be861e  alsa.tar.bz2' | sha256sum -c - \
    && tar -xf alsa.tar.bz2 && cd alsa-lib-1.2.15.3 \
    && patch --fuzz=0 -p1 < /src/alsa-ctlparse.patch \
    && patch --fuzz=0 -p1 < /src/alsa-sparse-bindings.patch \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --sysconfdir=/etc --disable-static --disable-topology \
        CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIC' LDFLAGS='-Wl,-z,relro,-z,now' \
    && make -j2 && make check && make DESTDIR=/backlog-install install
RUN curl --fail --location --retry 2 -o cups.tar.gz https://archive.ubuntu.com/ubuntu/pool/main/c/cups/cups_2.4.16.orig.tar.gz \
    && echo '0339587204b4f9428dd0592eb301dec0bf9ea6ea8dce5d9690d56be585aba92d  cups.tar.gz' | sha256sum -c - \
    && curl --fail --location --retry 2 -o cups-debian.tar.xz https://archive.ubuntu.com/ubuntu/pool/main/c/cups/cups_2.4.16-1ubuntu1.3.debian.tar.xz \
    && echo '08e5525d0e8b76dcd1842dc044b01f7cc9a962469dc7198f009508515b456312  cups-debian.tar.xz' | sha256sum -c - \
    && tar -xf cups.tar.gz && cd cups-2.4.16 \
    && tar -xf /src/cups-debian.tar.xz && QUILT_PATCHES=debian/patches quilt push -a \
    && patch --fuzz=0 -p1 < /src/cups-utf32.patch \
    && ./configure --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu --disable-static --disable-systemd --disable-libusb --disable-dbus --enable-gssapi \
        CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 -fPIC' LDFLAGS='-Wl,-z,relro,-z,now' \
    && make -j2 -C cups all \
    && mkdir -p /backlog-install/usr/lib/x86_64-linux-gnu \
    && cp -a cups/libcups.so.2 /backlog-install/usr/lib/x86_64-linux-gnu/
COPY security/package_backlog.py /src/
RUN python3 /src/package_backlog.py

FROM maintained-medium-runtime AS maintained-backlog-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=backlog-native-build /backlog-out/*.deb /tmp/backlog-security/
COPY --from=backlog-native-build /backlog-out/abi-check.json /usr/share/lms-security/backlog-abi-check.json
RUN dpkg -i /tmp/backlog-security/*.deb && ldconfig && apt-get check \
    && test -z "$(dpkg --audit)" && rm -rf /tmp/backlog-security
USER 10001:10001

FROM backlog-native-build AS backlog-extra-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext autopoint texinfo unicode-data libgcrypt20-dev libgpg-error-dev libassuan-dev libksba-dev libnpth0-dev libreadline-dev libsqlite3-dev \
    gpg meson ninja-build libglib2.0-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    && rm -rf /var/lib/apt/lists/*
COPY security/gnupg-cleartext.patch /src/
RUN echo '88af0682a98daa78f0407710af149e0283c1b54f98c71b7dbd6329be3f31d64a  gnupg-cleartext.patch' | sha256sum -c -
RUN curl --fail --location --retry 2 -o gnupg.tar.bz2 https://gnupg.org/ftp/gcrypt/gnupg/gnupg-2.4.8.tar.bz2 \
    && echo 'b58c80d79b04d3243ff49c1c3fc6b5f83138eb3784689563bcdd060595318616  gnupg.tar.bz2' | sha256sum -c - \
    && curl --fail --location --retry 2 -o gnupg-debian.tar.xz https://archive.ubuntu.com/ubuntu/pool/main/g/gnupg2/gnupg2_2.4.8-4ubuntu3.1.debian.tar.xz \
    && echo 'e7aa12d4e58ac906c89efc5d8b6c005ddd03b53e6eae8998ec871f902c6fea95  gnupg-debian.tar.xz' | sha256sum -c - \
    && tar -xf gnupg.tar.bz2 && cd gnupg-2.4.8 \
    && tar -xf /src/gnupg-debian.tar.xz && QUILT_PATCHES=debian/patches quilt push -a \
    && patch --fuzz=0 -p1 < /src/gnupg-cleartext.patch \
    && autoreconf -fi \
    && ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --libexecdir=/usr/lib/gnupg --disable-doc --disable-scdaemon --disable-g13 --disable-dirmngr --disable-gpgsm \
        CFLAGS='-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3' LDFLAGS='-Wl,-z,relro,-z,now'
RUN make -j2 -C /src/gnupg-2.4.8/common && make -j2 -C /src/gnupg-2.4.8/regexp \
    && make -j2 -C /src/gnupg-2.4.8/kbx && make -j2 -C /src/gnupg-2.4.8/g10 gpg gpgv
RUN apt-get update && apt-get install -y --no-install-recommends gpgv && rm -rf /var/lib/apt/lists/*
COPY security/rtsp_regression.c security/package_backlog_extra.py /src/
# Ubuntu 1.28.2-1ubuntu0.3 and later carry the RTSP fix (CVE-2026-85150) that this image
# used to backport. The regression cases now run against Ubuntu's own library.
# The compiler flags must split into separate words.
# hadolint ignore=SC2046
RUN gcc -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3 /src/rtsp_regression.c \
    $(pkg-config --cflags --libs gstreamer-1.0 gstreamer-rtsp-1.0) \
    -Wl,-z,relro,-z,now -o /src/rtsp-regression \
    && /src/rtsp-regression
RUN python3 /src/package_backlog_extra.py && cp /src/rtsp-regression /extra-out/

FROM maintained-backlog-runtime AS maintained-extra-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
COPY --from=backlog-extra-build /extra-out/*.deb /tmp/backlog-extra/
COPY --from=backlog-extra-build /extra-out/provenance.json /usr/share/lms-security/backlog-extra-provenance.json
RUN dpkg -i /tmp/backlog-extra/*.deb && ldconfig && apt-get check \
    && test -z "$(dpkg --audit)" && rm -rf /tmp/backlog-extra
USER 10001:10001

FROM maintained-extra-runtime AS maintained-priority-runtime
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER 0:0
# Ubuntu now ships the Poppler and GStreamer fixes this image used to rebuild by hand.
# Fail the build if an older package was installed.
# pebble (Canonical's service manager) ships in the Ubuntu base image, is owned by no
# package and is not used by the LMS; it carried the only Go standard library in the image.
RUN dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libpoppler156)" ge 26.01.0-2ubuntu0.3 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libgstreamer-plugins-base1.0-0)" ge 1.28.2-1ubuntu0.3 \
    && ! dpkg-query -W -f='${Version}' libpoppler156 libgstreamer-plugins-base1.0-0 | grep -q lms \
    && rm -f /usr/bin/pebble
COPY --from=lxml-build /out/lxml-source-build.json /usr/share/lms-security/lxml-source-build.json
COPY --from=python-parsers-build /out/pillow-source-build.json /usr/share/lms-security/pillow-source-build.json
COPY security/check_native_bundle_lock.py security/native-bundle-lock.json /usr/share/lms-security/
# Reference identities and reviewed-source output manifests are not CVE exemptions.
RUN python /usr/share/lms-security/check_native_bundle_lock.py \
        --lock /usr/share/lms-security/native-bundle-lock.json \
        > /usr/share/lms-security/native-bundle-identity.json \
    || { cat /usr/share/lms-security/native-bundle-identity.json; exit 1; }
# Third-party licence notices and supplier inventory, including the bundled browser build.
COPY security/write_notices.py /usr/share/lms-security/write_notices.py
RUN python /usr/share/lms-security/write_notices.py /usr/share/lms-security/notices
USER 10001:10001
