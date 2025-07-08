# --- STAGE 1: Builder ---
# This stage installs all dependencies.
FROM python:3.12-slim as builder

ENV PYTHONUNBUFFERED=True \
    PYTHONDONTWRITEBYTECODE=True \
    PIP_NO_CACHE_DIR=True \
    PIP_DISABLE_PIP_VERSION_CHECK=True

# Install system dependencies required for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- STAGE 2: Final ---
# This stage builds the final, lean image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=True \
    PYTHONDONTWRITEBYTECODE=True \
    PYTHONPATH=/app \
    PORT=8080 \
    FLASK_ENV=production

# Install only necessary runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user to run the application
RUN useradd --create-home --shell /bin/bash --uid 1000 app

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY --chown=app:app . .

# Create the logs directory and set ownership for the 'app' user
RUN mkdir -p /app/logs 
RUN chown -R app:app /app

# Switch to the non-root user
USER app

# Expose the port the app runs on
EXPOSE $PORT

# The command to run the application directly with Gunicorn
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:application"]