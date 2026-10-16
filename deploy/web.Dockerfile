# Builds one React app from the pnpm workspace and serves it with nginx.
# Build context is the repository root. Pass APP=trainer or APP=employee.
FROM node:24.21.0-alpine3.24@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/trainer/package.json apps/trainer/
COPY apps/employee/package.json apps/employee/
COPY packages/shared/package.json packages/shared/
RUN pnpm install --frozen-lockfile --ignore-scripts

COPY tsconfig.base.json tsconfig.json ./
COPY packages packages
COPY apps apps
ARG APP
ARG API_BASE_URL=
RUN test "$APP" = trainer || test "$APP" = employee
RUN VITE_API_BASE_URL="$API_BASE_URL" pnpm --filter "@lms/$APP" build

FROM nginxinc/nginx-unprivileged:1.31.6-alpine3.24@sha256:6a23acdfca2b9cfbcec61419e3f1426bcbedb91362f2f19306a8567423bb4612
USER root
RUN apk upgrade --no-cache
ARG APP
# An empty trusted edge address accepts no client-supplied forwarded scheme.
ENV TRUSTED_EDGE_PROXY_IP=""
COPY apps/${APP}/nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/apps/${APP}/dist /usr/share/nginx/html

EXPOSE 8080
USER 101
HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
