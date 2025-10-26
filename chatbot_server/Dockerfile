FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY app.py run.sh ./
RUN chmod +x run.sh

EXPOSE 5000
CMD ["./run.sh"]

