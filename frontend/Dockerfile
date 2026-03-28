# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── Stage 2: Serve ───────────────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

# BACKEND_HOST: "localhost" for ECS (same task), "backend" for docker-compose
ENV BACKEND_HOST=localhost

EXPOSE 80

# Replace BACKEND_UPSTREAM placeholder with actual host:port, then start nginx
CMD sh -c "sed 's|BACKEND_UPSTREAM|'\"$BACKEND_HOST\"':8000|g' \
    /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf \
    && nginx -g 'daemon off;'"
