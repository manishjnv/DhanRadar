FROM node:22-alpine AS deps
WORKDIR /app
# No package-lock.json committed for the Phase-1 skeleton — use `npm install`.
# A lockfile will be committed (and this switched back to `npm ci`) once the
# frontend dependency set is frozen in a later phase.
COPY package.json ./
RUN npm install

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# next.config.js sets `output: "standalone"`, so .next/standalone/server.js is
# the entrypoint. `public/` always exists (committed .gitkeep) so this COPY is
# unconditional and valid Dockerfile syntax.
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
