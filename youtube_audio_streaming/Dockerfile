ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Copy application files
COPY server.py requirements.txt /app/
COPY www /app/www
COPY run.sh /

# Make script executable
RUN chmod a+x /run.sh

# Install system dependencies
RUN apk add --no-cache ffmpeg

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# ✅ Install yt-dlp initially (will auto-update later)
RUN pip3 install --no-cache-dir yt-dlp

# Show initial version
RUN echo "📦 Initial yt-dlp version:" && yt-dlp --version

CMD ["/run.sh"]
