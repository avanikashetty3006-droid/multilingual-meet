FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models/hf
WORKDIR /app
COPY requirements.txt requirements-real.txt ./
RUN pip install -r requirements.txt \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements-real.txt
COPY . .
# NLLB must be converted once into /models/nllb-600m-ct2 (see README "Docker"); mount a volume on /models.
ENV NLLB_CT2_DIR=/models/nllb-600m-ct2 AUDIO_DIR=/tmp/audio
RUN useradd -m vaak && mkdir -p /models /tmp/audio && chown -R vaak /app /models /tmp/audio
USER vaak
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/v1/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
