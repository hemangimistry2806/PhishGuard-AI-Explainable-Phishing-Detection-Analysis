# ==============================================================================
# PhishGuard AI — Frontend Production Multi-Stage Dockerfile
# ==============================================================================

# Stage 1: Build production React/Vite bundle
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies with layer caching
COPY package.json package-lock.json* ./
RUN npm install

# Pass build-time environment variables
# Defaulting to empty string instructs frontend to use relative reverse-proxy routes
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Copy frontend source code
COPY . .

# Build production bundle to /app/dist
RUN npm run build

# Stage 2: Production web server with Nginx
FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built static artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose Vite's conventional port 5173
EXPOSE 5173

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:5173/nginx-health || exit 1

# Run Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
