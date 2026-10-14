FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS build

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git unzip xz-utils zip libglu1-mesa ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Match the SDK required by pubspec.lock and verify the immutable upstream revision.
RUN git clone --depth 1 --branch 3.44.0 https://github.com/flutter/flutter.git /usr/local/flutter \
    && test "$(git -C /usr/local/flutter rev-parse HEAD)" = 559ffa3f75e7402d65a8def9c28389a9b2e6fe42
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"
# Cache the SDK/web artifacts independently of each application's dependency lockfile.
RUN flutter config --no-analytics \
    && flutter precache --web

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get --enforce-lockfile

COPY . .
ARG API_BASE_URL=
RUN printf "API_BASE_URL=%s\n" "$API_BASE_URL" > .env \
    && flutter build web --release --no-pub --pwa-strategy=none --no-web-resources-cdn

FROM nginxinc/nginx-unprivileged:1.31.6-alpine3.24@sha256:6a23acdfca2b9cfbcec61419e3f1426bcbedb91362f2f19306a8567423bb4612
USER root
RUN apk upgrade --no-cache
# An empty trusted edge address accepts no client-supplied forwarded scheme.
ENV TRUSTED_EDGE_PROXY_IP=""
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/build/web /usr/share/nginx/html

EXPOSE 8080
USER 101
HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
