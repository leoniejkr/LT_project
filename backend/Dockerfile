# ============================== DEV =====================================
FROM golang:1.26 AS dev

# Installiere air für Live-Reload
RUN go install github.com/air-verse/air@latest

WORKDIR /app

# Kopiere die Abhängigkeiten
COPY go.mod go.sum ./
RUN go mod download


# Der Rest wird über "Volumes" reingereicht (siehe docker-compose)
CMD ["air", "-c", "air.toml"]

# ============================== PROD ====================================
FROM golang:1.26 AS build

WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .

ARG CGO_ENABLED=0
RUN CGO_ENABLED=${CGO_ENABLED} GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server ./cmd/server

FROM alpine:3.21 AS prod

RUN apk add --no-cache ca-certificates tzdata \
    && addgroup -S app && adduser -S -G app app

WORKDIR /app

COPY --from=build /out/server ./server

USER app

EXPOSE 8080

CMD ["./server"]