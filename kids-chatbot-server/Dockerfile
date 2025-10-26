FROM python:3.11-alpine

# Install system dependencies
RUN apk add --no-cache \
    ffmpeg \
    gcc \
    musl-dev \
    linux-headers \
    bash

# Install Python packages
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    openai>=1.0.0 \
    python-dotenv==1.0.0 \
    gunicorn==21.2.0

# Copy rootfs
COPY rootfs /

# Make scripts executable
RUN chmod a+x /etc/services.d/app/run \
    /etc/services.d/app/finish \
    /usr/bin/app.py

WORKDIR /usr/bin

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1

# Run via s6-overlay
CMD ["/etc/services.d/app/run"]
