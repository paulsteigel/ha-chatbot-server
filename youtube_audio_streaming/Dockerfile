ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Copy application files
COPY server.py requirements.txt /app/
COPY www /app/www

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt
RUN apk add --no-cache ffmpeg

# Start command
CMD ["python3", "server.py"]
