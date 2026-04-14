# ── Stage 1: Build Frontend ───────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /build
# Install dependencies
COPY frontend/package*.json ./
RUN npm install
# Build frontend
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Final Production Image ───────────────────────────────────────────
FROM python:3.11-slim

# ── Environment ───────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# ── Setup ─────────────────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (cached layer) ───────────────────────────────────────
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
COPY backend/ /app/

# ── Bundled Frontend ──────────────────────────────────────────────────────────
# Copy the built React app from Stage 1 into the backend folder
COPY --from=frontend-builder /build/dist /app/frontend/dist

# ── Secret file mount point (Render writes here at runtime) ──────────────────
RUN mkdir -p /etc/secrets

# ── Port ──────────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
