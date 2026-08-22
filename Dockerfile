# ==============================================================================
# Stage 1: Builder
# ==============================================================================
FROM python:3.11-slim AS builder

# Prevent Python from writing pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# ==============================================================================
# Stage 2: Production Runner
# ==============================================================================
FROM python:3.11-slim

# Security and Optimization ENV vars
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies (wkhtmltopdf for PDF generation) and apply security updates
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends wkhtmltopdf curl && \
    rm -rf /var/lib/apt/lists/*

# Create a dedicated non-root user and group
RUN groupadd -r sre-user && useradd -r -g sre-user sre-user

# Install Python packages from builder stage
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir /wheels/*

# Copy application source code
COPY . /app

# Ensure correct ownership and permissions for the non-root user
RUN mkdir -p /app/data /app/reports /app/exports && \
    chown -R sre-user:sre-user /app

# Switch to the non-root user
USER sre-user

# Expose Streamlit port
EXPOSE 8501

# Healthcheck to verify Streamlit frontend is active
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Start Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
