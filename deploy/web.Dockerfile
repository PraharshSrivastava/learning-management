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
# The second command records licences and authors of the bundled packages for the notice file.
RUN VITE_API_BASE_URL="$API_BASE_URL" pnpm --filter "@lms/$APP" build \
    && pnpm --filter "@lms/$APP" licenses list --prod --json > /app/third-party-licenses.json

FROM nginxinc/nginx-unprivileged:1.31.6-alpine3.24@sha256:884e0b7f42f303641b0f4e78755aea647521dca0b89ca3be7992ad78b5c07434
USER 0
RUN apk upgrade --no-cache
ARG APP
# An empty trusted edge address accepts no client-supplied forwarded scheme.
ENV TRUSTED_EDGE_PROXY_IP=""
COPY apps/${APP}/nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/apps/${APP}/dist /usr/share/nginx/html
COPY --from=build /app/third-party-licenses.json /usr/share/licenses/lms/third-party-licenses.json

EXPOSE 8080
USER 101
HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD ["wget", "-qO-", "http://127.0.0.1:8080/"]
CMD ["nginx", "-g", "daemon off;"]
