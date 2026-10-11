# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (fonts for Pillow image rendering and SSL certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (leverage Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and local credentials if present
COPY api.py card_generator.py constants.py ui_views.py db_logger.py plague.py ./
COPY .env* keys.env* ./

# Create data directory for SQLite persistence and non-privileged user
RUN mkdir -p /app/data && useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

# Run the bot
CMD ["python", "plague.py"]
