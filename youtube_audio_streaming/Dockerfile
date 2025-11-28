ARG BUILD_FROM
FROM $BUILD_FROM

# Install additional dependencies if needed
RUN apk add --no-cache ffmpeg

WORKDIR /app

# Copy application files
COPY server.py requirements.txt /app/

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
