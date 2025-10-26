ARG BUILD_FROM
FROM $BUILD_FROM

# Environment
ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    libsndfile \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /usr/bin

# Copy requirements first (for Docker layer caching)
COPY rootfs/usr/bin/requirements.txt .

# Install Python packages
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY rootfs /

# Make run script executable
RUN chmod a+x /run.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python3 -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Start
CMD ["/run.sh"]
