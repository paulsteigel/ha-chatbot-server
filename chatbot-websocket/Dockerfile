ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    ffmpeg \
    build-base \
    && rm -rf /var/cache/apk/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY run.sh /

RUN chmod +x /run.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

CMD ["/run.sh"]
