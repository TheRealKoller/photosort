FROM node:22-bookworm-slim

# `libcurl4` ist die Laufzeitabhängigkeit des SDK für die Lizenzmeldung an Desert Ant Labs.
# Die GEWICHTE kommen NICHT ins Image (S4): das Verzeichnis wird als Volume gemountet, gepinnt
# ist nur ihr SHA-256 in `src/pins.json`.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libcurl4 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY src ./src

ENV NODE_ENV=production \
    DAL_APP_ID=photosort \
    EYE_MODEL_DIR=/model \
    EYE_PORT=8090

USER node
EXPOSE 8090

CMD ["node", "src/server.js"]
