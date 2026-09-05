# ============================== DEV =====================================
# Wir nutzen Node.js als Basis
FROM node:22 AS dev

WORKDIR /app

# Nur die Package-Dateien kopieren, um den Cache optimal zu nutzen
COPY package*.json ./

# Dependencies installieren
RUN npm install

# Den Rest des Codes kopieren
COPY . .

# Next.js Standard-Port
EXPOSE 3000

# Startbefehl für die Entwicklung
CMD ["npm", "run", "dev"]

# ============================== PROD ====================================
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Auf den Node-Server-Adapter (SSR) umschalten
ENV ADAPTER=node
RUN npm run build

FROM node:22-alpine AS prod

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

WORKDIR /app

# Nur die Produktions-Abhängigkeiten in das Laufzeit-Image
COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=build /app/build ./build

# Der SSR-Server des SvelteKit-Builds (adapter-node)
USER node

EXPOSE 3000

CMD ["node", "build"]