ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11
FROM $BUILD_FROM

RUN apk add --no-cache \
    ffmpeg \
    && rm -rf /var/cache/apk/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY run.sh /
RUN chmod +x /run.sh

EXPOSE 5000

CMD ["/run.sh"]
