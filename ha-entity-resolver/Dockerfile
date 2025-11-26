ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /usr/bin

# Copy requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application
COPY rootfs /

# Make run script executable
RUN chmod +x /usr/bin/run.sh

CMD ["/usr/bin/run.sh"]
