# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Set working directory
WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt-get/lists/*

# Copy requirements file first for layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Expose port (Cloud Run defaults to 8080)
EXPOSE 8080

# Run FastAPI app with Uvicorn (exec ensures process replaces shell for signal handling and Cloud Run $PORT)
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
