# Production web image: the built frontend, served by nginx, which also
# terminates TLS and proxies /api to the API and /media to object storage.
# Build from the repository root:  docker build -f nginx/Dockerfile .

FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM nginx:1.27-alpine
# openssl: the stand-in certificate used until Let's Encrypt issues the real one
RUN apk add --no-cache openssl
COPY nginx/templates/ /etc/nginx/templates/
COPY nginx/snippets/ /etc/nginx/snippets/
COPY --chmod=755 nginx/certs.sh /docker-entrypoint.d/40-certs.sh
COPY --from=build /app/dist /usr/share/nginx/html
