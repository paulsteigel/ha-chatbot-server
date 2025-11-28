ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

COPY server.py requirements.txt /app/
COPY www/ /app/www/

RUN pip3 install --no-cache-dir -r requirements.txt

# Copy s6 service file
COPY run /etc/services.d/youtube_audio/run
RUN chmod a+x /etc/services.d/youtube_audio/run
