ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    bash \
    ffmpeg \
    gcc \
    musl-dev \
    linux-headers \
    mysql-client \
    mariadb-connector-c-dev \
    pkgconfig

# Copy requirements first (for Docker layer caching)
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# Copy application files
COPY rootfs /

# Make service scripts executable
RUN chmod a+x /etc/services.d/app/run /etc/services.d/app/finish

# Set working directory
WORKDIR /usr/bin

# Health check - internal container check
# Vì có proxy ra ngoài nên check internal để đảm bảo app đang chạy
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/api/health || exit 1
