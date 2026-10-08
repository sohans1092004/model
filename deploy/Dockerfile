# UDK live detection service (api.py): English + custom UDK, and on a GPU host Hindi + Telugu/Tamil/Kannada.
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
# ~3.5 GB of weights baked into the image: no downloads when the service starts.
# Optional fine-tuned intent model (+1.1 GB) from a private HF repo, see deploy/README.md.
ARG UDK_INTENT_MODEL_REPO=
ARG UDK_INTENT_MODEL_REVISION=
# Host-dependent models (remote_deploy.sh sets them from the host's settings): the custom-UDK gate's own Whisper
# (e.g. medium.en on a GPU) and, with 1, the multilingual models (language-ID Whisper small, IndicConformer,
# LaBSE, MuRIL + the pinned [B] weights; ~6 GB, private / gated on Hugging Face, so they need the hf_token secret).
ARG UDK_PREFETCH_CUSTOM_STT=
ARG UDK_PREFETCH_MULTILINGUAL=0
# No Xet downloads: huggingface_hub 1.x keeps Xet files in a shared hub/blobs/ store but plain-git files in the
# repo's own blobs/, and onnxruntime >= 1.24 refuses an .onnx whose external weights sit in another directory
# (IndicConformer: .onnx via Xet, its weight files via git). Without Xet both land in the repo's blobs/.
RUN --mount=type=secret,id=hf_token,required=false     if [ -f /run/secrets/hf_token ]; then export HF_TOKEN="$(cat /run/secrets/hf_token)"; fi;     HF_HUB_DISABLE_XET=1 python deploy/prefetch_models.py

# cuBLAS / cuDNN come with torch's pip wheels (site-packages/nvidia), off the library path: torch and onnxruntime
# find them themselves, ctranslate2 (Whisper) only through LD_LIBRARY_PATH -- without this it falls back to CPU.
ENV LD_LIBRARY_PATH=/opt/conda/lib/python3.11/site-packages/nvidia/cublas/lib:/opt/conda/lib/python3.11/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}

VOLUME /data
EXPOSE 8000
# ONE worker: live journeys are held in this process's memory
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
