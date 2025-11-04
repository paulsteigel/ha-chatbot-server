ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    python3-dev \
    py3-pip \
    ffmpeg \
    build-base \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Create virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY run.sh /

# Make run script executable
RUN chmod +x /run.sh

# Expose port
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

CMD ["/run.sh"]
