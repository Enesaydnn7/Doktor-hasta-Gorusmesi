# Docker tabanlı ücretsiz platformlar için (Hugging Face Spaces, Koyeb, Fly.io...).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render $PORT verir; Hugging Face Spaces varsayılan 7860 kullanır.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}
