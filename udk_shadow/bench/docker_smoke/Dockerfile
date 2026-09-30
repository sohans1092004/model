# SMOKE image for Phase 6C (not the production image): same build context and the SAME whitelist
# (a byte-identical copy of deploy/Dockerfile.dockerignore next to this file), light CPU dependencies only,
# no model weights (Hugging Face is unreachable here). Proves which files the whitelist ships and that
# api.py + shadow start from them.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app UDK_DATA_DIR=/data
RUN --mount=type=secret,id=ca,required=false if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; pip install --no-cache-dir fastapi httpx "uvicorn[standard]" numpy rapidfuzz webrtcvad-wheels "setuptools<81" cryptography
COPY . .
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
