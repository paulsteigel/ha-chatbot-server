FROM python:3.11-slim-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system dependencies for Azure Speech SDK
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    ca-certificates \
    libasound2 \
    wget \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/app/
COPY static/ /app/static/

# ✅ REMOVED: COPY main.py /app/ (vì main.py đã ở trong app/)

# Create directories with proper permissions
RUN mkdir -p /app/logs /app/models && \
    chmod -R 777 /app/logs /app/models

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

LABEL \
    org.opencontainers.image.title="School Chatbot Server" \
    org.opencontainers.image.description="Standalone Docker with Azure Speech SDK" \
    org.opencontainers.image.source="https://github.com/paulsteigel/ha-chatbot-server" \
    org.opencontainers.image.authors="Đặng Đình Ngọc <ngocdd@sfdp.net>"

# ✅ FIXED: Run from app/main.py
CMD ["python", "-m", "app.main"]
