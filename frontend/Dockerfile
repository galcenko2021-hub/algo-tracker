# syntax=docker/dockerfile:1

# ---- build stage ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- runtime stage: unprivileged nginx serves the static bundle and proxies /api ----
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
