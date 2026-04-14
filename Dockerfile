# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── Environment ───────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# ── Setup ─────────────────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (cached layer) ───────────────────────────────────────
# Copy requirements from the backend folder
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
# Copy everything from the backend folder into the container
COPY backend/ /app/

# ── Secret file mount point (Render writes here at runtime) ──────────────────
RUN mkdir -p /etc/secrets

# ── Port ──────────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
