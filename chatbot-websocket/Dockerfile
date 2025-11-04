ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies
RUN apk add --no-cache \
    ffmpeg \
    && rm -rf /var/cache/apk/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Copy static files
COPY static/ /static/

# Copy s6-overlay service
COPY rootfs /

# Make run script executable
RUN chmod a+x /etc/services.d/chatbot/run

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5000/health || exit 1
# Install dependencies with fixed versions
RUN pip3 install --no-cache-dir \
    websockets==12.0 \
    aiohttp==3.9.1 \
    python-dotenv==1.0.0 \
    gTTS==2.5.0 \
    openai==1.54.0 \
    httpx==0.27.0 \
    pydantic==2.9.0 \
    typing-extensions==4.12.2
