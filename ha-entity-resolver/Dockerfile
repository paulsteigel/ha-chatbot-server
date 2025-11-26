ARG BUILD_FROM
FROM $BUILD_FROM

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install bashio and dependencies
RUN apk add --no-cache \
    python3=~3.11 \
    py3-pip \
    bash \
    curl \
    jq

# Install bashio
RUN curl -s https://raw.githubusercontent.com/hassio-addons/bashio/master/lib/bashio.sh -o /usr/lib/bashio.sh \
    && chmod +x /usr/lib/bashio.sh

WORKDIR /app

# Copy and install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application
COPY app/ /app/

# Copy rootfs
COPY rootfs /

# Fix permissions
RUN chmod a+x /etc/services.d/resolver/run

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5003/health || exit 1

LABEL \
  io.hass.name="HA Entity Resolver" \
  io.hass.description="Resolve entity names to MQTT topics for ESP32 bots" \
  io.hass.version="1.0.2" \
  io.hass.type="addon" \
  io.hass.arch="armhf|aarch64|i386|amd64|armv7"
