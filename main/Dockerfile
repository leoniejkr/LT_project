# Schlankes Python-Image
FROM python:3.13

WORKDIR /app

# System-Abhängigkeiten (falls nötig)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Anforderungen kopieren und installieren
# Erstelle am besten eine requirements.txt in dem Ordner
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Den Code kopieren
COPY . .

EXPOSE 5000

# Startet deine Python-App (z.B. Flask oder FastAPI)
CMD ["python", "main.py"]