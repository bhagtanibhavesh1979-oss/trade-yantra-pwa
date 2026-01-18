# Trade Yantra - Simplified Cloud Run Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Non-buffered logs
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Start the app - Use explicit app reference for Cloud Run
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
