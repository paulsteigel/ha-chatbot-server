ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    && pip3 install --no-cache-dir --upgrade pip

# Copy requirements
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy application
COPY rootfs /

# Set working directory
WORKDIR /

# Make script executable
RUN chmod a+x /app.py

CMD ["python3", "/app.py"]