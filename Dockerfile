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
    python-dotenv==1.0.0

# Copy rootfs
COPY rootfs /

# Make scripts executable
RUN chmod a+x /usr/bin/run.sh /usr/bin/app.py

# Set working directory
WORKDIR /usr/bin

# Run the application
CMD ["/usr/bin/run.sh"]
