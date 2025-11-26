ARG BUILD_FROM
FROM $BUILD_FROM

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    curl

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ /app/

# Copy rootfs
COPY rootfs /

# Set permissions
RUN chmod a+x /etc/services.d/resolver/run

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5003/health || exit 1

LABEL \
  io.hass.version="1.0.0" \
  io.hass.type="addon" \
  io.hass.arch="armhf|aarch64|i386|amd64|armv7"
