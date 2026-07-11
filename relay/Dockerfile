# Hermes Dist Relay — Docker image
# Multi-stage: build deps, then runtime with just uvicorn + the app

FROM python:3.11-slim AS runtime

WORKDIR /app

# Install only what we need
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app
COPY app/ ./app/

# Create the data directory (will be mounted as a volume)
RUN mkdir -p /var/lib/hermes-relay && \
    useradd -r -s /bin/false relay && \
    chown -R relay:relay /var/lib/hermes-relay
USER relay

# Default port
EXPOSE 9119

# Environment defaults (overridable)
ENV RELAY_DB_PATH=/var/lib/hermes-relay/relay.db
ENV PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:9119/api/v1/healthz', timeout=3).raise_for_status()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9119", "--workers", "1"]
