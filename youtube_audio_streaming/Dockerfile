# Dùng image chính thức của Home Assistant
FROM ghcr.io/home-assistant/{arch}-addon-base-python:latest

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép các file cần thiết vào trong container
COPY . /app

# Cài đặt các dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Mở port 5000
EXPOSE 5000

# Chạy Flask app
CMD ["python3", "server.py"]
