# Dockerfile for Cloud Run deployment with ADK
FROM python:3.11-slim

WORKDIR /app

# Install dependencies from the frozen requirements.txt file
# This file is generated from poetry.lock to ensure exact versions are used.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for better security
RUN adduser --disabled-password --gecos "" myuser && \
    chown -R myuser:myuser /app

# Copy the application files in dependency order:
# 1. schemas.py - Root level schemas needed by both agent and shared_utils
# 2. shared_utils/ - Utilities used by the agent (depends on schemas.py)
# 3. refiner_agent/ - Main agent logic (depends on schemas.py and shared_utils/)
# 4. app.py - Unified entry point for Cloud Run deployment

COPY schemas.py .
COPY shared_utils/ ./shared_utils/
COPY refiner_agent/ ./refiner_agent/
COPY app.py .

# Additional project directories are copied as needed

# Switch to non-root user
USER myuser

# Run the application using the unified app.py
# This auto-detects Cloud Run environment via K_SERVICE env var and uses PORT (default 8080)
CMD ["python", "app.py"]