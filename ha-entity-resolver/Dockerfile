ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /

# Copy requirements first (for better caching)
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy entire rootfs structure
COPY rootfs /

# Make run script executable
RUN chmod a+x /usr/bin/run.sh

# Set working directory for app
WORKDIR /usr/bin

CMD ["/usr/bin/run.sh"]
