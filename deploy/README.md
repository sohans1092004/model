# Deploying the UDK live detection service

One Docker image: `api.py` + the 20 modules it needs, with all model weights baked in.
The website integration is described in the "UDK Detection API: Integration Guide" doc.

## What's in the image
Exactly the files listed in `Dockerfile.dockerignore` (a whitelist). Check it's complete
before every build; this needs no Docker or GPU:
```
python deploy/check_package.py
```

## Server needs
- NVIDIA GPU (the evaluations ran on a T4, 16 GB), driver for CUDA 12, Docker + NVIDIA Container Toolkit
- ~15 GB disk for the image, plus the data volume
- HTTPS in front (nginx / Caddy / a cloud load balancer), which also carries the WebSocket;
  uvicorn itself serves plain HTTP on port 8000

## Build and run
```
docker build -f deploy/Dockerfile -t udk-api .          # from the Model folder; ~15-25 min, downloads ~3.5 GB of models
cp deploy/.env.example .env                             # fill UDK_SERVICE_TOKEN, UDK_WEBHOOK_URL, UDK_WEBHOOK_SECRET
docker run -d --name udk --gpus all --restart unless-stopped \
  --env-file .env -p 8000:8000 -v udk-data:/data udk-api
```

## Check it after starting
```
docker logs udk 2>&1 | grep -iE "warn|error|cuda"       # a warning that STT fell back to CPU = GPU not used
curl -H "X-Service-Token: $TOKEN" http://localhost:8000/metrics
```
Then stream one prepped_data clip through it (colab_api_check.py does this in-process)
and confirm the alert arrives at the webhook.

## Rules for running it
- **One worker, one container per GPU.** Live sessions are held in memory; two workers
  would split a session's audio. More users -> more containers with a load balancer that
  keeps each journey on one container (route by journey_id).
- **Back up the `/data` volume, keys included.** It holds the encryption keys
  (`udk_audio.key`, `udk_db.key`), the signing secret, the SQLite DB, audio and the alert
  retry queue. Losing the keys makes stored audio and events unreadable. With
  `UDK_DATABASE_URL` / `UDK_S3_*` set, the DB and audio live outside, but the keys still
  live in `/data`.
- **Secrets:** the service refuses to start with an empty token, the public dev token,
  a non-HTTPS webhook URL, or a webhook without a secret.

## Not in this image
Evaluation/test/Colab code, the distress detector and intent model (not validated yet),
non-English models, SepFormer separation, and `udk_endpoint.py` (clip upload service).
