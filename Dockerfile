# Multi-stage Dockerfile for Berry AI Studio
# Stage 1: Build Frontend Assets
FROM node:20-slim AS frontend-builder
WORKDIR /build

# Enable corepack for pnpm package manager
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy frontend dependency manifests and install dependencies
COPY frontend/package.json frontend/pnpm-lock.yaml* ./frontend/
WORKDIR /build/frontend
RUN pnpm install --frozen-lockfile || pnpm install

# Copy frontend source code and compile production distribution
COPY frontend/ ./
RUN pnpm run build

# Stage 2: Python Backend Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Install system dependencies including curl for container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend source code
COPY backend/ ./backend/

# Copy compiled frontend assets from builder stage
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Set default runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    BERRY_PORT=8000 \
    BERRY_DATA_DIR=/app/data \
    LOG_LEVEL=INFO

# Create data directory and define volume for persistence
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8000

# Health check probe against /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Uvicorn ASGI server
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
