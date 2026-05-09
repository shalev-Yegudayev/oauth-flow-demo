# ── Stage 1: Node builder ─────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies before copying source to leverage layer cache
COPY package*.json ./
RUN npm ci

# Vite bakes env vars into the bundle at build time, so they must be
# available here — not at container start.
ARG VITE_BACKEND_API_BASE_URL=http://localhost:8000
ENV VITE_BACKEND_API_BASE_URL=$VITE_BACKEND_API_BASE_URL

COPY . .
RUN npm run build

# ── Stage 2: Nginx static server ──────────────────────────────────────────────
FROM nginx:alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
