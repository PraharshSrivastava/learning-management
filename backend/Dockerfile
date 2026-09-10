FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg=7:7.1.5-0+deb13u1 \
        libreoffice-writer=4:25.2.3-2+deb13u6 \
        libreoffice-impress=4:25.2.3-2+deb13u6 \
        fonts-dejavu-core=2.37-8 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --require-hashes -r requirements.lock \
    && python -m playwright install --with-deps chromium

COPY app ./app
COPY scripts ./scripts

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/storage \
    && chown -R app:app /app /ms-playwright

EXPOSE 8000

USER app

HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
