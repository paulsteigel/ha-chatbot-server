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

# Copy application files
COPY rootfs /

# Ensure scripts are executable
RUN chmod a+x /etc/services.d/ha-entity-resolver/run /etc/services.d/ha-entity-resolver/finish

# No CMD - let s6-overlay handle it
