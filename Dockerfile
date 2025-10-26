ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    jq \
    curl \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /usr/bin

# Copy requirements first for better caching
COPY rootfs/usr/bin/requirements.txt .

# Install Python packages
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy ALL rootfs content
COPY rootfs/ /

# Make run script executable
RUN chmod a+x /run.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Start
CMD ["/run.sh"]
