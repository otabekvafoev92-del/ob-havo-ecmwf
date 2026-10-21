FROM node:24-slim AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY app ./app
COPY components ./components
COPY lib ./lib
COPY public ./public
COPY telegram ./telegram
COPY scripts/build-telegram.mjs ./scripts/build-telegram.mjs
COPY postcss.config.mjs ./
RUN node scripts/build-telegram.mjs

FROM node:24-slim
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/telegram-dist ./telegram-dist
COPY telegram/auth.mjs telegram/weather.mjs telegram/bot.mjs telegram/server.mjs ./telegram/
COPY lib/weather.ts lib/weather-map.ts ./lib/
USER node
EXPOSE 3000
CMD ["node","telegram/server.mjs"]
