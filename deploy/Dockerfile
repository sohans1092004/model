# UDK live detection service (api.py), English, GPU.
# Build from the Model folder (the file whitelist is deploy/Dockerfile.dockerignore; needs BuildKit):
#   docker build -f deploy/Dockerfile -t udk-api .
# CUDA 12 + cuDNN 9: what ctranslate2 (Whisper) and onnxruntime-gpu < 1.27 (Parakeet) need.
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app HF_HOME=/app/hf_cache UDK_DATA_DIR=/data

COPY deploy/requirements-deploy.txt deploy/
RUN pip install --no-cache-dir torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124 \
 && pip install --no-cache-dir -r deploy/requirements-deploy.txt \
 # onnx-asr pulls CPU onnxruntime; a leftover folder breaks the GPU build's import, so remove it first
 && pip uninstall -y onnxruntime onnxruntime-gpu \
 && rm -rf "$(python -c 'import site; print(site.getsitepackages()[0])')/onnxruntime" \
 && pip install --no-cache-dir --no-deps "onnxruntime-gpu>=1.22,<1.27,!=1.24.1,!=1.25.*,!=1.26.0"

COPY . .
# ~3.5 GB of weights baked into the image: no downloads when the service starts
RUN python deploy/prefetch_models.py

VOLUME /data
EXPOSE 8000
# ONE worker: live journeys are held in this process's memory
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
