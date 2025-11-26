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

# Ensure run.sh is executable (fix GitHub edit issue)
RUN chmod +x /usr/bin/run.sh /usr/bin/app.py

# Set working directory
WORKDIR /usr/bin

# Run directly without s6
CMD ["python3", "-u", "app.py"]
