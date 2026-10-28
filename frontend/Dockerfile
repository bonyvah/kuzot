# Vite dev server (live reload). For a static prod build, see the commented
# stage at the bottom and serve ./dist via nginx instead.
FROM node:22-alpine

WORKDIR /app
RUN corepack enable

# Install deps first for layer caching. node_modules is excluded by
# .dockerignore and kept in an anonymous volume (see docker-compose.yml).
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173
# --host binds 0.0.0.0 so the port is reachable from outside the container.
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]

# ─── Production build (optional) ───────────────────────────────────
# FROM node:22-alpine AS build
# WORKDIR /app
# RUN corepack enable
# COPY package.json pnpm-lock.yaml ./
# RUN pnpm install --frozen-lockfile
# COPY . .
# RUN pnpm build
# FROM nginx:alpine
# COPY --from=build /app/dist /usr/share/nginx/html
