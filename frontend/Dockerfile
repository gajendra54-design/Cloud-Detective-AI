FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund --fetch-retries=3 --fetch-timeout=120000
COPY frontend/ ./
RUN npm run build
FROM nginxinc/nginx-unprivileged:1.30.6-alpine
USER root
# The dashboard only serves static assets and proxies HTTP; no XML or njs modules.
RUN apk upgrade --no-cache zlib \
    && apk del --no-cache curl nginx-module-xslt nginx-module-njs
USER 101
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
