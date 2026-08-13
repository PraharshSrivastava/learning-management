FROM ubuntu:22.04 AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git unzip xz-utils zip libglu1-mesa ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch 3.24.5 https://github.com/flutter/flutter.git /usr/local/flutter
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get

COPY . .
ARG API_BASE_URL=
ARG USE_SAME_ORIGIN_API=false
RUN printf "API_BASE_URL=%s\nUSE_SAME_ORIGIN_API=%s\n" "$API_BASE_URL" "$USE_SAME_ORIGIN_API" > .env \
    && flutter build web --release

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
