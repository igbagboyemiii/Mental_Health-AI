# ─────────────────────────────────────────────────────────────
# Dockerfile — MindGuard FastAPI Backend
# ─────────────────────────────────────────────────────────────
# Build:  docker build -t mindguard-api .
# Run:    docker-compose up
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies for faiss-cpu and pynput
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create a persistent volume mount point for the SQLite DB
RUN mkdir -p /data
ENV DB_PATH=/data/monitor_history.db

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
