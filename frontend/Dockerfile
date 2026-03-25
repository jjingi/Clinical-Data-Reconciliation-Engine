# ── Stage 1: build ──────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json .
RUN npm ci

# VITE_API_KEY is baked into the JS bundle at build time
ARG VITE_API_KEY
ENV VITE_API_KEY=$VITE_API_KEY

COPY . .
RUN npm run build

# ── Stage 2: serve ──────────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
