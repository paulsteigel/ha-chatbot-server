ARG BUILD_FROM
FROM $BUILD_FROM

# Install only essential dependencies
RUN apk add --no-cache \
    ffmpeg \
    && rm -rf /var/cache/apk/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY run.sh /

RUN chmod +x /run.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

# Let s6-overlay handle the startup - DO NOT override CMD
