#!/bin/bash
# Runs ON the sakhi-udk (CPU) or sakhi-udk-gpu instance, from a release deploy/aws_deploy.py unpacked there over SSM:
#   bash deploy/remote_deploy.sh <release> <region>
# Builds the image (skipped if this release is already built), swaps the container, and rolls
# back to the previous one if the new one never answers. SSM keeps this output: print no secret.
set -euo pipefail
REL=$1 REGION=$2
ETC=${UDK_ETC:-/etc/udk}  # root-only (the bootstrap made it 700); overridable to test this script
export PATH=$PATH:/snap/bin
# The intent model the settings were calibrated on; change only when Sohan publishes a new one.
INTENT_REPO=sohans1092004/udk-intent-mdeberta
INTENT_REVISION=6131acc0f5c583d3ef24b7da1f293d207f26a08b

exec 9> "$ETC/deploy.lock"
flock -n 9 || { echo "another deploy is running" >&2; exit 1; }
cd "$(dirname "$0")/.."
umask 077

# The snap-packaged aws CLI writes nothing into a file it inherits as stdout (AppArmor denies
# snap-confine the descriptor) and still exits 0, so its output always goes through a pipe.
ssm() { aws ssm get-parameter --region "$REGION" --name "$1" --with-decryption --query Parameter.Value --output text | cat; }

# Secrets and host settings live in SSM; the GPU stack's bootstrap names its own parameter in $ETC/config-param.
CONFIG_PARAM=$(cat $ETC/config-param 2> /dev/null || echo /sakhi/udk/config)
ssm "$CONFIG_PARAM" > $ETC/ssm.env
grep -q '^UDK_SERVICE_TOKEN=.' $ETC/ssm.env || { echo "$CONFIG_PARAM has no UDK_SERVICE_TOKEN" >&2; exit 1; }
# The repo's validated detection settings override SSM, except HOST settings: what this hardware runs (device,
# the custom-UDK gate's model, the Hindi / Telugu-Tamil-Kannada branches, where the text models sit, CPU threads).
# The CPU host's SSM sets none of the multilingual ones, so it keeps running the English + custom-UDK service.
# Secrets are blank in .env.example, so SSM's values for them always stand.
HOST_KEYS='UDK_DEVICE|UDK_CUSTOM_UDK_STT_MODEL|UDK_ENABLE_HINDI|UDK_ENABLE_INDIC_EXACT|UDK_HINDI_DEVICE|UDK_TEXT_MODELS_DEVICE|UDK_CPU_THREADS'
grep -E '^[A-Z0-9_]+=.+' deploy/.env.example | grep -Ev "^($HOST_KEYS)=" > $ETC/repo.env
awk -F= '/^[A-Z0-9_]+=/ { if (!($1 in v)) k[++n] = $1; v[$1] = $0 } END { for (i = 1; i <= n; i++) print v[k[i]] }' \
  $ETC/ssm.env $ETC/repo.env > $ETC/run.env.new

# Models baked into the image follow this host's settings, so the service never downloads at start:
# the custom-UDK gate's own Whisper, and the multilingual models when Hindi or Telugu/Tamil/Kannada is on.
setting() { grep -E "^$1=" $ETC/run.env.new | tail -1 | cut -d= -f2- || true; }
CUSTOM_STT=$(setting UDK_CUSTOM_UDK_STT_MODEL)
MULTILINGUAL=0
{ [ "$(setting UDK_ENABLE_HINDI)" = 1 ] || [ -n "$(setting UDK_ENABLE_INDIC_EXACT)" ]; } && MULTILINGUAL=1
GPU_ARGS=()
[ "$(setting UDK_DEVICE)" = cuda ] && GPU_ARGS=(--gpus all)

# The intent model is in a private HF repo: built in only once its read token is in SSM.
BUILD_ARGS=(--build-arg "UDK_PREFETCH_CUSTOM_STT=$CUSTOM_STT" --build-arg "UDK_PREFETCH_MULTILINGUAL=$MULTILINGUAL")
TAG=$REL${CUSTOM_STT:+-$CUSTOM_STT}
[ "$MULTILINGUAL" = 1 ] && TAG=$TAG-ml
if hf=$(ssm /sakhi/udk/hf-token 2>&1); then
  [[ $hf == hf_* ]] || { echo "/sakhi/udk/hf-token is not an HF token" >&2; exit 1; }
  printf '%s' "$hf" > $ETC/hf_token
  BUILD_ARGS+=(--build-arg "UDK_INTENT_MODEL_REPO=$INTENT_REPO" --build-arg "UDK_INTENT_MODEL_REVISION=$INTENT_REVISION"
               --secret id=hf_token,src=$ETC/hf_token)
  TAG=$TAG-intent
else
  # The multilingual models are private / gated on Hugging Face: without the token they cannot be built in.
  [ "$MULTILINGUAL" = 1 ] && { echo "Hindi / Telugu-Tamil-Kannada are on but /sakhi/udk/hf-token is missing" >&2; exit 1; }
  echo "no HF token ($(grep -oE 'ParameterNotFound|AccessDenied' <<< "$hf" | head -1)): building without the intent model"
fi

if ! docker image inspect "udk-api:$TAG" > /dev/null 2>&1; then
  echo "building udk-api:$TAG"
  DOCKER_BUILDKIT=1 docker build --progress=plain -f deploy/Dockerfile -t "udk-api:$TAG" "${BUILD_ARGS[@]}" . \
    > $ETC/build.log 2>&1 || { rm -f $ETC/hf_token; tail -40 $ETC/build.log >&2; exit 1; }
  grep -E 'intent model|prefetched|all models cached' $ETC/build.log || true
fi
rm -f $ETC/hf_token

current=$(docker inspect -f '{{.Config.Image}}' udk 2> /dev/null || true)
previous_env=$ETC/run.env
[ -f "$previous_env" ] || previous_env=$ETC/udk.env  # the bootstrap's file, before the first deploy
if [ "$current" = "udk-api:$TAG" ] && cmp -s $ETC/run.env.new $ETC/run.env \
   && [ "$(docker inspect -f '{{.State.Running}}' udk)" = true ]; then
  echo "already running udk-api:$TAG with this config"
  exit 0
fi

start() {  # image, env file. Live journeys are lost here; the website reconnects with new ones.
  docker rm -f udk > /dev/null 2>&1 || true
  docker run -d --name udk --network udk --restart unless-stopped "${GPU_ARGS[@]}" --env-file "$2" -p 127.0.0.1:8000:8000 \
    -v udk-data:/data --log-opt max-size=50m --log-opt max-file=3 "$1" > /dev/null
}
ready() {  # a 401 to a wrong token = models loaded and serving
  for _ in $(seq 90); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' -H 'X-Service-Token: deploy-probe' http://127.0.0.1:8000/metrics)" = 401 ] && return 0
    sleep 10
  done
  return 1
}

# A container that cannot even start (e.g. --gpus on a host without the driver) rolls back too:
# by then the old one is already removed.
if ! start "udk-api:$TAG" $ETC/run.env.new || ! ready; then
  echo "udk-api:$TAG never became ready; its last log lines:" >&2
  docker logs --tail 30 udk >&2 2>&1 || true
  if [ -n "$current" ]; then start "$current" "$previous_env" && echo "rolled back to $current" >&2; fi
  exit 1
fi
mv $ETC/run.env.new $ETC/run.env
docker logs udk 2>&1 | grep -E 'intent gate|fell back to CPU|failed on CUDA' || true

# Keep only the running image; the layers it shares with the next build stay cached.
docker images udk-api --format '{{.Repository}}:{{.Tag}}' | grep -vx "udk-api:$TAG" | xargs -r docker rmi > /dev/null || true
docker image prune -f > /dev/null
df -h / | tail -1
echo "deployed udk-api:$TAG"
