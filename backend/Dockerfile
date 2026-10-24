# ==============================================================================
# PhishGuard AI — Backend Production Dockerfile
# ==============================================================================

FROM python:3.10-slim

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    DATABASE_URL=sqlite:////app/data/phishguard.db \
    MODEL_PATH=/app/ml/models/xgboost_model.pkl \
    PYTHONPATH=/app/backend:/app

WORKDIR /app

# Install system dependencies (libgomp1 required for XGBoost OpenMP runtime, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user for defense-in-depth
RUN useradd -u 1000 -m appuser

# Prepare persistent data and reports directories with proper ownership
RUN mkdir -p /app/data /app/ml/models /app/backend/reports \
    && chown -R appuser:appuser /app

# Install Python requirements with Docker layer caching
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code and model artifacts into expected project paths
COPY backend/ /app/backend/
COPY ml/models/ /app/ml/models/

# Ensure all application files are owned by appuser
RUN chown -R appuser:appuser /app

# Run as non-root user
USER appuser

# Work directory where app.py resides
WORKDIR /app/backend

# Expose API port
EXPOSE 8000

# Backend container health check
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Launch FastAPI via uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
