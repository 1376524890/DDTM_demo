FROM node:22.16-bookworm-slim

ENV NODE_ENV=production
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund \
 && npm cache clean --force

COPY src ./src
RUN useradd --system --uid 10001 --create-home ddtm \
 && chown -R ddtm:ddtm /app

USER ddtm
EXPOSE 8080
CMD ["node", "src/server.js"]
