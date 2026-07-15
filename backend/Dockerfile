FROM golang:1.26 AS dev

# Installiere air für Live-Reload
RUN go install github.com/air-verse/air@latest

WORKDIR /app

# Kopiere die Abhängigkeiten
COPY go.mod go.sum ./
RUN go mod download



# Der Rest wird über "Volumes" reingereicht (siehe docker-compose)
CMD ["air", "-c", "air.toml"]