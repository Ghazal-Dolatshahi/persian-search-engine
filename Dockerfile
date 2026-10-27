FROM docker.arvancloud.ir/library/python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    INDEX_PATH=/index/index.pkl

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 \
    -i https://mirror-pypi.runflare.com/simple \
    --trusted-host mirror-pypi.runflare.com \
    -r requirements.txt

COPY app ./app
RUN mkdir -p /data /index

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
