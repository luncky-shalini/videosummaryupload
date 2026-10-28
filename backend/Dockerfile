# Production Dockerfile for backend service (Render / Railway / Fly.io / VPS)
FROM python:3.12-slim

# Install system dependencies including FFmpeg, curl, and Unicode fonts for PDF reports
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    curl \
    fonts-dejavu-core \
    fonts-noto-cjk \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Support both root context (docker build -f backend/Dockerfile .) and subfolder context
COPY requirements.txt* backend/requirements.txt* /tmp/
RUN if [ -f /tmp/requirements.txt ]; then \
        pip install --no-cache-dir -r /tmp/requirements.txt; \
    elif [ -f /tmp/backend/requirements.txt ]; then \
        pip install --no-cache-dir -r /tmp/backend/requirements.txt; \
    fi && rm -rf /tmp/*

COPY . /app/
# If code was copied under /app/backend, flatten it to /app
RUN if [ -d /app/backend ] && [ -f /app/backend/main.py ]; then \
        cp -r /app/backend/* /app/ && rm -rf /app/backend; \
    fi

# Ensure uploads directory exists
RUN mkdir -p /app/uploads

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
