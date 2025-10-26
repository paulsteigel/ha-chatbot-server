ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    bash \
    ffmpeg \
    gcc \
    musl-dev \
    linux-headers

# Install Python packages
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    openai>=1.0.0 \
    python-dotenv==1.0.0

# Copy application files
COPY rootfs /

# Make service scripts executable
RUN chmod a+x /etc/services.d/app/run /etc/services.d/app/finish
