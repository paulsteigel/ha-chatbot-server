FROM python:3.11-alpine

# Install dependencies
RUN apk add --no-cache bash curl

# Set working directory
WORKDIR /app

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.py .

# Expose port
EXPOSE 5003

# Run directly
CMD ["python3", "run.py"]
