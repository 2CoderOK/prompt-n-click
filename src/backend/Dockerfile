FROM python:3.11-slim

WORKDIR /app

# Install OS-level sqlite3 support and ffmpeg for audio processing
RUN apt-get update && apt-get install -y sqlite3 libsqlite3-dev ffmpeg && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app
COPY shared/ /app/shared

ENV PYTHONPATH="/app"
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]