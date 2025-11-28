ARG BUILD_FROM
FROM $BUILD_FROM

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép các file cần thiết
COPY server.py requirements.txt /app/

# Cài đặt dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy và set permission cho run script
COPY run.sh /etc/services.d/youtube_audio/run
RUN chmod a+x /etc/services.d/youtube_audio/run
