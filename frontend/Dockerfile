# Multi-stage build: React/Vite bundle -> nginx.
# IMPORTANT: VITE_* variables are baked into the JS at BUILD time, so they are build ARGs (not runtime env).
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline --no-audit

COPY . .

ARG VITE_GOOGLE_CLIENT_ID
ARG VITE_API_BASE_URL=/api
ARG VITE_LIVEKIT_URL=
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_LIVEKIT_URL=$VITE_LIVEKIT_URL \
    VITE_API_MOCK=0
RUN test -n "$VITE_GOOGLE_CLIENT_ID" || (echo "ERROR: build arg VITE_GOOGLE_CLIENT_ID is empty" && exit 1)
RUN npm run build

FROM nginx:1.27-alpine-slim
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /app/dist /usr/share/nginx/html
# *.template files are run through envsubst at container start (only variables that exist in the environment)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80
