FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    RFP_DATA_ROOT=/bids RFP_DATA_DIR=/data RFP_OUTPUT_DIR=/outputs
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# CPU wheels avoid shipping unnecessary CUDA runtimes on the EC2 host.
COPY requirements-linux.txt ./
RUN python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.1 \
    && python -m pip install -r requirements-linux.txt
COPY pyproject.toml ./
COPY rfp_intelligence ./rfp_intelligence
COPY eval ./eval
RUN python -m pip install --no-deps . \
    && useradd --uid 10001 --create-home app \
    && mkdir -p /bids /data /outputs \
    && chown -R app:app /data /outputs
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "rfp_intelligence.cli", "serve", "--host", "0.0.0.0"]
