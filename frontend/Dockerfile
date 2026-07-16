# --- Stage 1: Build -----------------------------------------------------------
FROM node:22-slim AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

# Dependencies first (layer-cached unless manifests change). Dev deps are
# required here: vite, svelte-kit and adapter-node all live in devDependencies.
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile --ignore-scripts || pnpm install --ignore-scripts

# Source + production build. Every env var this app reads is dynamic
# (\$env/dynamic/*), resolved at runtime from the container process env, so
# nothing has to be baked in at build time.
COPY . .
ENV NODE_ENV=production
RUN pnpm build

# Strip dev dependencies so only runtime deps travel to the final image.
RUN pnpm prune --prod

# --- Stage 2: Run -------------------------------------------------------------
FROM node:22-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=5173
ENV HOST=0.0.0.0

# adapter-node output + the pruned runtime deps.
COPY --from=builder /app/build ./build
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

RUN groupadd -r app && useradd -r -g app app && chown -R app:app /app
USER app

EXPOSE 5173

CMD ["node", "build"]
