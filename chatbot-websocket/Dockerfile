ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install Python and required system packages
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-setuptools \
    py3-wheel \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/app/

# Copy static files
COPY static/ /app/static/

RUN mkdir -p /app/models && chmod 777 /app/models

# Copy rootfs (S6 overlay scripts)
COPY rootfs /

# Set executable permissions for service scripts
RUN chmod +x /etc/services.d/chatbot/run && \
    chmod +x /etc/services.d/chatbot/finish

# Expose port
EXPOSE 5000

# Labels
LABEL \
    io.hass.name="School Chatbot WebSocket Server" \
    io.hass.description="WebSocket server for ESP32-based school chatbot with AI integration" \
    io.hass.version="1.0.0" \
    io.hass.type="addon" \
    io.hass.arch="armhf|aarch64|amd64"
