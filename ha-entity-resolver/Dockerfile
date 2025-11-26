ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    && rm -rf /var/cache/apk/*

# Copy requirements and install
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy application
COPY rootfs /

# Ensure executable permissions
RUN chmod +x /usr/bin/app.py

# Set working directory
WORKDIR /usr/bin

# Run Python directly
CMD ["python3", "-u", "app.py"]
