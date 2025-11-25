FROM python:3.9-slim

# Cài đặt các thư viện cần thiết
RUN pip install Flask requests

# Sao chép mã nguồn Python vào container
COPY run.py /app/run.py

# Chạy mã nguồn của app
WORKDIR /app
CMD ["python", "run.py"]
