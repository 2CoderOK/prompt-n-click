# Use the official Python 3.12 slim image
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# --- FIX: Added build-essential and gcc ---
RUN apt-get update && apt-get install -y \
    git \
    wget \
    ffmpeg \
    libsndfile1 \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Install PyTorch specifically compiled for CUDA 12.4
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 2. Install VoxCPM
RUN pip install --no-cache-dir voxcpm

# 3. Install FastAPI + Uvicorn
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# Copy our files
COPY . /app/

# Serve the FastAPI app
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8091"]