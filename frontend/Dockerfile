# ==============================================================================
# Multi-Stage Dockerfile for VAAK Production Frontend
# ==============================================================================

# Stage 1: Build React / Vite application
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package descriptors first for Docker layer caching
COPY package.json package-lock.json* ./

RUN npm ci --prefer-offline --no-audit

COPY . .

# Build production bundle with route-level code splitting
RUN npm run build

# Stage 2: Minimal Nginx web server
FROM nginx:alpine-slim

# Remove default nginx website
RUN rm -rf /usr/share/nginx/html/*

# Copy built artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy optimized nginx reverse proxy & CSP configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
