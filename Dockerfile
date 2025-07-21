# Multi-stage Dockerfile for WebWunder container deployment

# Build stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy Python packages from builder and make them accessible
COPY --from=builder /root/.local /home/appuser/.local
RUN chown -R appuser:appuser /home/appuser/.local

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
RUN chown -R appuser:appuser /app

USER appuser

# Set Python path and ensure packages are available
ENV PYTHONPATH=/app
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUSERBASE=/home/appuser/.local

# Environment variables
ENV APP_ENVIRONMENT=production
ENV PORT=8080
ENV WS_PORT=8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose ports
EXPOSE 8080 8081

# Default command (HTTP server)
CMD ["python", "-m", "src.presentation.http_server"]