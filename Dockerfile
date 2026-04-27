FROM python:3.12-slim

WORKDIR /app

# Install system deps for networking tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    nmap \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY phantom/ ./phantom/
COPY configs/ ./configs/

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[api]"

# Create data directories
RUN mkdir -p /root/.phantom-strike/reports /root/.phantom-strike/evidence /root/.phantom-strike/logs

# Expose port
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:10000/health || exit 1

# Run the API server
CMD ["uvicorn", "phantom.api.enhanced_server:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1"]
