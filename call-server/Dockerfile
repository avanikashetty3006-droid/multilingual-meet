# Build context is the REPO ROOT (see docker-compose.yml) because the server reads ../shared/config.yaml.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/call-server

COPY call-server/requirements.txt .
RUN pip install -r requirements.txt

COPY call-server/ /app/call-server/
COPY shared/ /app/shared/

RUN useradd -m vaak && chown -R vaak /app
USER vaak

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/v1/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
