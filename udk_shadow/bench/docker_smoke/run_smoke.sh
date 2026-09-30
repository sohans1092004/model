#!/bin/bash
# Usage (from the repo root): bash udk_shadow/bench/docker_smoke/run_smoke.sh   [OUT=dir] [CA_BUNDLE=/path/ca.pem if TLS is intercepted]
# Builds a SMOKE image (python:3.11-slim, light deps, no weights) from the SAME context and a byte-identical copy of
# deploy/Dockerfile.dockerignore, then runs the shadow deployment checks. Not the production image.
# Phase 6C deployment smoke test against the smoke image. Prints PASS/FAIL per check.
OUT=${OUT:-$(mktemp -d)}; HERE=$(cd "$(dirname "$0")" && pwd)
IMG=udk-api-smoke:6c
cd "$HERE/../../.."
cp deploy/Dockerfile.dockerignore $HERE/Dockerfile.dockerignore
cmp deploy/Dockerfile.dockerignore $HERE/Dockerfile.dockerignore || { echo "FAIL whitelist copy differs"; exit 1; }
DOCKER_BUILDKIT=1 docker build --network host ${CA_BUNDLE:+--secret id=ca,src=$CA_BUNDLE} -q -f $HERE/Dockerfile -t $IMG . > $OUT/build.log 2>&1 || { echo "FAIL build"; tail -20 $OUT/build.log; exit 1; }
ENVS="-e UDK_SERVICE_TOKEN=check-token -e UDK_WEBHOOK_URL=https://example.invalid/hook -e UDK_WEBHOOK_SECRET=s"
res() { if [ "$1" = 0 ]; then echo "PASS $2"; else echo "FAIL $2"; fi; }
# 1. what the image contains
docker run --rm --network host $IMG sh -c 'cd /app && find udk_shadow udk_fusion udk_context udk_signals asr_bench -type f | sort' > $OUT/files.txt
grep -q "udk_shadow/runner.py" $OUT/files.txt && ! grep -qE "(^|/)test_|report\.py|evaluation\.py|README|OPEN_ITEMS|fixture|(^|/)bench/|splits\.py" $OUT/files.txt
res $? "image ships shadow runtime files only ($(wc -l < $OUT/files.txt) files; no tests/reports/eval/fixtures/benchmark)"
PROBE="from fastapi.testclient import TestClient; import api; c = TestClient(api.app); assert c.get('/metrics', headers={'X-Service-Token': 'check-token'}).status_code == 200"
# 2. shadow OFF (default)
docker run --rm --network host $ENVS $IMG python -c "$PROBE; import sys; assert api._shadow is None and 'udk_shadow' not in sys.modules" > /dev/null 2>&1
res $? "shadow OFF (default): service starts, shadow not imported"
# 3. shadow ON
out=$(docker run --rm --network host $ENVS -e UDK_SHADOW_MODE=1 $IMG python -c "$PROBE; assert api._shadow is not None; print(api._shadow.processor.effective['s4_status'], api._shadow.processor.effective['sentence_veto']['phase5_sentence_veto_guard'])" 2>&1)
echo "$out" | grep -q "shadow mode ON (udk_shadow, self-check ok)" && echo "$out" | grep -q "^open False"
res $? "shadow ON: runtime loads, start-up self-check ok, effective S-4=open, Phase 5 sentence-veto guard=False"
# 4. missing shadow package
docker run --rm --network host $ENVS -e UDK_SHADOW_MODE=1 $IMG sh -c "rm -rf /app/udk_fusion && python -c \"$PROBE; assert api._shadow is None\"" > /dev/null 2>&1
res $? "shadow ON + udk_fusion missing: fails closed (shadow OFF), service serves"
# 5. missing shadow dependency module
docker run --rm --network host $ENVS -e UDK_SHADOW_MODE=1 $IMG sh -c "rm -f /app/asr_bench/textnorm.py && python -c \"$PROBE; assert api._shadow is None\"" > /dev/null 2>&1
res $? "shadow ON + a shadow dependency missing (asr_bench/textnorm.py): fails closed, service serves"
# 6. bad shadow config
docker run --rm --network host $ENVS -e UDK_SHADOW_MODE=1 -e UDK_SHADOW_QUEUE_MAX=0 $IMG python -c "$PROBE; assert api._shadow is None" > /dev/null 2>&1
res $? "shadow ON + invalid shadow config: fails closed, service serves"
# 7. real server process with shadow ON (uvicorn), probe over HTTP
cid=$(docker run -d --network host $ENVS -e UDK_SHADOW_MODE=1 $IMG)
for i in $(seq 30); do code=$(docker exec $cid python -c "import urllib.request as u
try: u.urlopen(u.Request('http://127.0.0.1:8000/metrics', headers={'X-Service-Token': 'check-token'})); print(200)
except Exception as e: print(getattr(e, 'code', 0))" 2>/dev/null); [ "$code" = 200 ] && break; sleep 1; done
docker logs $cid 2>&1 | grep -q "shadow mode ON (udk_shadow, self-check ok)"; logok=$?
docker rm -f $cid > /dev/null
[ "$code" = 200 ] && [ $logok = 0 ]; res $? "uvicorn server with shadow ON answers /metrics (200) and logs the self-check"
# 8. isolation tests executed against the IMAGE's code (test files mounted read-only; not in the image)
docker run --rm --network host -v $PWD/udk_shadow/test_shadow.py:/app/udk_shadow/test_shadow.py:ro -v $PWD/udk_shadow/report.py:/app/udk_shadow/report.py:ro \
  $IMG python udk_shadow/test_shadow.py > $OUT/iso.txt 2>&1
res $? "shadow test suite (live-path isolation, failure isolation) run against the image code: $(tail -1 $OUT/iso.txt)"
# 9. live-service smoke INSIDE the image: real api, real hook, websocket streaming; OFF / ON / stage error / queue full / missing pkg
docker run --rm --network host -e UDK_SERVICE_TOKEN=check-token -v $PWD/udk_shadow/bench/smoke_live_service.py:/app/udk_shadow/bench/smoke_live_service.py:ro \
  $IMG python udk_shadow/bench/smoke_live_service.py > $OUT/live_service.json 2>&1
res $? "live-service smoke in the image: $(tail -1 $OUT/live_service.json)"
