# Ollama-Image um curl erweitert, damit beim Start das GGUF-Modell vom
# Hugging Face Hub geladen werden kann (siehe docker-compose.yaml -> ollama).
FROM ollama/ollama

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*