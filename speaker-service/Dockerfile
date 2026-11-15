# Build context is the REPO ROOT (see docker-compose.yml): config.py reads ../shared/config.yaml.
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/speaker-service

COPY speaker-service/requirements.txt .
RUN pip install -r requirements.txt

COPY speaker-service/ /app/speaker-service/
COPY shared/ /app/shared/

RUN useradd -m vaak && chown -R vaak /app
USER vaak

# MOCK=0 = real Silero VAD (the 1.3 MB ONNX model is bundled in models/). Set by docker-compose.
ENV SPEAKER_HOST=0.0.0.0 SPEAKER_PORT=8002
EXPOSE 8002
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8002/v1/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
