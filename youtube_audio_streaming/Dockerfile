ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

COPY server.py requirements.txt /app/

RUN pip3 install --no-cache-dir -r requirements.txt

COPY run.sh /etc/services.d/youtube_audio/run
RUN chmod a+x /etc/services.d/youtube_audio/run
