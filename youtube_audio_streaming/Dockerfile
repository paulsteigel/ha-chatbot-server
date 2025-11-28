FROM ghcr.io/home-assistant/amd64-base-python:3.13-alpine3.20

WORKDIR /app

COPY server.py requirements.txt /app/

RUN pip3 install --no-cache-dir -r requirements.txt

# Copy s6 service files
COPY run /etc/services.d/youtube_audio/run
RUN chmod a+x /etc/services.d/youtube_audio/run
