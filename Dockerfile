# Disability Schemes Assistant — production image.
# Runs on Render (free tier, see render.yaml), Azure, Google Cloud Run, a VPS,
# or a Hugging Face Docker Space. Set GROQ_API_KEY as a secret.
# No PyTorch: embeddings run as ONNX (fastembed), so it fits in 512 MB RAM.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed \
    OMP_NUM_THREADS=1 \
    PORT=7860

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Bake the embedding + reranker models into the image (fast cold starts).
RUN python scripts/warm_models.py

# Run as a non-root user (also what Hugging Face Spaces expects: uid 1000).
RUN useradd -m -u 1000 app && chown -R app:app /app /tmp
USER app

EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"7860\")}/api/health')"

# Hosts set $PORT (Render: 10000); 7860 is the default elsewhere.
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
