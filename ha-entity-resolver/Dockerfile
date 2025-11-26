ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    curl \
    jq

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app/ /app/
COPY rootfs/ /

# Convert line endings and set permissions
RUN dos2unix /etc/services.d/resolver/run /etc/services.d/resolver/finish 2>/dev/null || true && \
    chmod +x /etc/services.d/resolver/run /etc/services.d/resolver/finish

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:5003/health || exit 1