FROM python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 AS python-runtime
# Same Ubuntu base, Python and fonts as the backend image had, so video frames keep their look.
FROM ubuntu:26.04@sha256:f144425ff09be612d6d9ad965196e9cdc23dae1f42110a8a11a3e9a8198759f7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        ca-certificates tzdata fonts-dejavu-core \
        libbz2-1.0 libffi8 liblzma5 libsqlite3-0 libssl3t64 zlib1g libexpat1 libuuid1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-runtime /usr/local/ /usr/local/
RUN ldconfig && python -c "import ssl, sqlite3, bz2, lzma, ctypes, uuid, pyexpat; print(ssl.OPENSSL_VERSION)"

COPY requirements.lock ./
# Only the headless shell: it is the binary Playwright launches for headless=True.
# Playwright's FFmpeg only records browser video, which the renderer never does.
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --require-hashes -r requirements.lock \
    && python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /ms-playwright/ffmpeg-* \
    && apt-get purge -y xvfb xserver-common \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip check \
    && python -m pip uninstall --yes pip

COPY server.py ./

RUN groupadd --system --gid 10001 renderer \
    && useradd --system --uid 10001 --gid renderer --create-home --home-dir /home/renderer \
        --shell /usr/sbin/nologin renderer

EXPOSE 8080

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5)"

CMD ["python", "server.py"]
