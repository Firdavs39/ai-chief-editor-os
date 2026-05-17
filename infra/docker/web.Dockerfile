FROM node:22-alpine AS base
RUN corepack enable && corepack prepare pnpm@10.15.1 --activate

FROM base AS deps
WORKDIR /repo
COPY apps/web/package.json apps/web/pnpm-lock.yaml* ./apps/web/
RUN cd apps/web && pnpm install --frozen-lockfile || pnpm install

FROM base AS builder
WORKDIR /repo
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY apps/web ./apps/web
WORKDIR /repo/apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm run build

FROM base AS runner
WORKDIR /repo/apps/web
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /repo/apps/web/.next ./.next
COPY --from=builder /repo/apps/web/public ./public
COPY --from=builder /repo/apps/web/node_modules ./node_modules
COPY --from=builder /repo/apps/web/package.json ./package.json
COPY --from=builder /repo/apps/web/next.config.mjs ./next.config.mjs
EXPOSE 3000
CMD ["pnpm", "start"]
