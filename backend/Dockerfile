FROM python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

# The base image is digest-pinned; use current distribution security updates at build time.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libreoffice-writer \
        libreoffice-impress \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --require-hashes -r requirements.lock \
    && python -m playwright install --with-deps chromium

COPY app ./app
COPY scripts ./scripts

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/storage \
    && chown -R app:app /app /ms-playwright

EXPOSE 8000

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
