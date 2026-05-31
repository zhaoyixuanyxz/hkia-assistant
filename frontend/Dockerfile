ARG NODE_IMAGE=node:22-alpine
ARG NPM_REGISTRY=https://registry.npmjs.org/

FROM ${NODE_IMAGE} AS deps
ARG NPM_REGISTRY
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ "$NPM_REGISTRY" != "https://registry.npmjs.org/" ]; then npm config set registry "$NPM_REGISTRY"; fi && npm ci

FROM ${NODE_IMAGE} AS builder
ARG NPM_REGISTRY
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN if [ "$NPM_REGISTRY" != "https://registry.npmjs.org/" ]; then npm config set registry "$NPM_REGISTRY"; fi && npm run build

FROM ${NODE_IMAGE} AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
