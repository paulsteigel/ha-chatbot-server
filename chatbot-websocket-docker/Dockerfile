FROM python:3.11-slim-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ✅ STEP 1: Install basic dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    libasound2 \
    wget \
    curl \
    ffmpeg \
    libgomp1 \
    libatomic1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# ✅ STEP 2: Install OpenSSL 1.1.1 (required by Azure Speech SDK)
# See: https://github.com/Azure-Samples/cognitive-services-speech-sdk/issues/2204
#RUN wget http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.0g-2ubuntu4_amd64.deb && \
#    dpkg -i libssl1.1_1.1.0g-2ubuntu4_amd64.deb && \
#    rm libssl1.1_1.1.0g-2ubuntu4_amd64.deb

RUN wget http://archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb && \
    dpkg -i libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb && \
    rm libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb
    
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/app/
COPY static/ /app/static/

# Create directories with proper permissions
RUN mkdir -p /app/logs /app/models && \
    chmod -R 777 /app/logs /app/models

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

LABEL \
    org.opencontainers.image.title="School Chatbot Server" \
    org.opencontainers.image.description="Standalone Docker with Azure Speech SDK + OpenSSL 1.1.1" \
    org.opencontainers.image.source="https://github.com/paulsteigel/ha-chatbot-server" \
    org.opencontainers.image.authors="Đặng Đình Ngọc <ngocdd@sfdp.net>"

CMD ["python", "-m", "app.main"]
