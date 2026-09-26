#!/bin/bash
# Runs ON the sakhi-udk instance, from a release deploy/aws_deploy.py unpacked there over SSM:
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

# Secrets and host settings (UDK_DEVICE=cpu) live in SSM.
ssm /sakhi/udk/config > $ETC/ssm.env
grep -q '^UDK_SERVICE_TOKEN=.' $ETC/ssm.env || { echo "/sakhi/udk/config has no UDK_SERVICE_TOKEN" >&2; exit 1; }
# The repo's validated detection settings override SSM, except UDK_DEVICE, which is the host's.
# Secrets are blank in .env.example, so SSM's values for them always stand.
grep -E '^[A-Z0-9_]+=.+' deploy/.env.example | grep -v '^UDK_DEVICE=' > $ETC/repo.env
awk -F= '/^[A-Z0-9_]+=/ { if (!($1 in v)) k[++n] = $1; v[$1] = $0 } END { for (i = 1; i <= n; i++) print v[k[i]] }' \
  $ETC/ssm.env $ETC/repo.env > $ETC/run.env.new

# The intent model is in a private HF repo: built in only once its read token is in SSM.
BUILD_ARGS=() TAG=$REL
if hf=$(ssm /sakhi/udk/hf-token 2>&1); then
  [[ $hf == hf_* ]] || { echo "/sakhi/udk/hf-token is not an HF token" >&2; exit 1; }
  printf '%s' "$hf" > $ETC/hf_token
  BUILD_ARGS=(--build-arg "UDK_INTENT_MODEL_REPO=$INTENT_REPO" --build-arg "UDK_INTENT_MODEL_REVISION=$INTENT_REVISION"
              --secret id=hf_token,src=$ETC/hf_token)
  TAG=$REL-intent
else
  echo "no HF token ($(grep -oE 'ParameterNotFound|AccessDenied' <<< "$hf" | head -1)): building without the intent model"
fi

if ! docker image inspect "udk-api:$TAG" > /dev/null 2>&1; then
  echo "building udk-api:$TAG"
  DOCKER_BUILDKIT=1 docker build --progress=plain -f deploy/Dockerfile -t "udk-api:$TAG" "${BUILD_ARGS[@]}" . \
    > $ETC/build.log 2>&1 || { rm -f $ETC/hf_token; tail -40 $ETC/build.log >&2; exit 1; }
  grep -E 'intent model|all models cached' $ETC/build.log || true
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
  docker run -d --name udk --network udk --restart unless-stopped --env-file "$2" -p 127.0.0.1:8000:8000 \
    -v udk-data:/data --log-opt max-size=50m --log-opt max-file=3 "$1" > /dev/null
}
ready() {  # a 401 to a wrong token = models loaded and serving
  for _ in $(seq 90); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' -H 'X-Service-Token: deploy-probe' http://127.0.0.1:8000/metrics)" = 401 ] && return 0
    sleep 10
  done
  return 1
}

start "udk-api:$TAG" $ETC/run.env.new
if ! ready; then
  echo "udk-api:$TAG never became ready; its last log lines:" >&2
  docker logs --tail 30 udk >&2 2>&1 || true
  if [ -n "$current" ]; then start "$current" "$previous_env" && echo "rolled back to $current" >&2; fi
  exit 1
fi
mv $ETC/run.env.new $ETC/run.env
docker logs udk 2>&1 | grep -E 'intent gate|fell back to CPU' || true

# Keep only the running image; the layers it shares with the next build stay cached.
docker images udk-api --format '{{.Repository}}:{{.Tag}}' | grep -vx "udk-api:$TAG" | xargs -r docker rmi > /dev/null || true
docker image prune -f > /dev/null
df -h / | tail -1
echo "deployed udk-api:$TAG"
