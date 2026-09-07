# Dockerfile

FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt /app/requirements.docker.txt

RUN pip install --no-cache-dir -r /app/requirements.docker.txt

# Install facenet-pytorch without forcing torch/torchvision reinstall.
RUN pip install --no-cache-dir --no-deps facenet-pytorch

COPY app /app/app
COPY scripts /app/scripts
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

RUN mkdir -p \
    /app/storage/models \
    /app/storage/artifacts \
    /app/storage/cache \
    /app/storage/db

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]