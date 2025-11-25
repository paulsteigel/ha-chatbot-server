ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and pip
RUN apk add --no-cache python3 py3-pip

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY run.py .

# Expose port
EXPOSE 5003

# Run the application
CMD ["python3", "run.py"]
