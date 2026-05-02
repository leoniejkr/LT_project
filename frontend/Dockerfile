# Wir nutzen Node.js als Basis
FROM node:24

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