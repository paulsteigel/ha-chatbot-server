FROM alpine:3.19

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-setuptools \
    ffmpeg \
    build-base \
    python3-dev \
    linux-headers \
    bash \
    && rm -rf /var/cache/apk/*

# Create symbolic link for python
RUN ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY run.sh /

RUN chmod +x /run.sh

EXPOSE 5000

# Simple healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD nc -z localhost 5000 || exit 1

CMD ["/run.sh"]
