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
export HF_TOKEN=hf_...                                   # read token for the private intent-model repo
docker build -f deploy/Dockerfile -t udk-api   --build-arg UDK_INTENT_MODEL_REPO=<hf-user>/udk-intent-mdeberta   --secret id=hf_token,env=HF_TOKEN .                    # from the Model folder; ~15-25 min, downloads ~4.6 GB of models
cp deploy/.env.example .env                             # fill UDK_SERVICE_TOKEN, UDK_WEBHOOK_URL, UDK_WEBHOOK_SECRET
docker run -d --name udk --gpus all --restart unless-stopped \
  --env-file .env -p 8000:8000 -v udk-data:/data udk-api
```

Without the two intent-model lines the image builds without mDeBERTa and runs with the
intent gate off (a warning in the logs); everything else is unchanged. The token is a build
secret: it is not stored in the image. `UDK_INTENT_MODEL_REVISION=<commit>` pins a model version.

## Check it after starting
```
docker logs udk 2>&1 | grep -iE "warn|error|cuda"       # a warning that STT fell back to CPU = GPU not used
curl -H "X-Service-Token: $TOKEN" http://localhost:8000/metrics
```
Then stream one prepped_data clip through it (colab_api_check.py does this in-process)
and confirm the alert arrives at the webhook.

## Optional features (all off in `.env.example`; deploying this code changes nothing until switched on)
**Custom UDK (each user's own phrase, `custom_udk.py`).** Off while `UDK_CUSTOM_UDK_STT_MODEL` is unset.
1. Put `UDK_CUSTOM_UDK_STT_MODEL` in the server config (SSM `/sakhi/udk/config`, not `.env.example`: it is per
   host): `small.en` on the CPU host, where it is the general model's own Whisper (shared, already in the image);
   `medium.en` on a GPU host (not in the image: the first start downloads ~1.5 GB, again after each redeploy).
2. The app calls `POST /v1/users/{user_id}/custom-udk/refresh` (service token) with
   `{"recordings": ["<base64 audio file>", ...]}` (4-6 files; wav/webm/m4a/mp3/ogg) after the user records, and
   shows `reason` when `accepted` is false; `heard` lists what each recording was heard as. `DELETE /v1/users/{user_id}/custom-udk` forgets a user's phrase.
3. Speed: with the same model as the general one (CPU host) the gate transcribes first and a miss reuses those
   transcripts; with its own model (medium.en on a GPU) it runs in parallel with language ID and the other paths. Measured per segment: medium.en on a T4 adds ~0.6-1.5 s; on CPU
   medium takes ~11-13 s and small.en ~4 s (laptop CPU).
4. Changing the model: each profile records its `stt`, journey start then answers `custom_udk: false` for older
   ones and the app asks those users to record again.
5. Rollback: this code drops `journeys.personal_udk_*` on its first start, and earlier images cannot start journeys
   on that DB. The automatic rollback is safe (the DB opens only after every model loads); a manual rollback to an
   earlier release needs the `/data` backup from before this one.

**Hindi (`safety_router/`, docs/hindi_distress_system.md).** Off: `UDK_ENABLE_HINDI=0` in `.env.example`, which
overrides SSM, so switching it on is a code change to that line.
- Needs a GPU host (see "GPU host" below): on 4 vCPU the full system takes ~21 s per segment. Everything fits one
  16 GB T4 with `UDK_TEXT_MODELS_DEVICE=cpu` (11.9 GB GPU peak measured; LaBSE, MuRIL and the intent veto on CPU).
- Its models (private [B] weights, gated IndicConformer) are baked into the image at build with the HF token
  (`/sakhi/udk/hf-token`); nothing downloads at start.
- If enabled but not loadable, the service refuses to start (and remote_deploy.sh rolls back).

**Telugu / Tamil / Kannada (exact or fuzzy match only).** Off while `UDK_ENABLE_INDIC_EXACT` is unset; set e.g.
`te,ta,kn` (any subset). They join the per-segment language ID like Hindi; a routed segment is transcribed by
IndicConformer in that language and matched only against that language's 20 phrases (exact or fuzzy; no semantic
matching, no context model, no intent veto). A match only ever asks "Are you safe?" (`TRIGGER_VERIFY`, layer e.g.
`te_exact`), never a direct alert, and never lowers an English or Hindi alert on the same segment. Shares Hindi's
IndicConformer when Hindi is on, otherwise loads it; same GPU and `HF_TOKEN` needs as Hindi. Not yet measured on
real Telugu/Tamil/Kannada audio.

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

## The live AWS deployment (Sakhi)
CloudFormation stack `sakhi-udk` (`sakhi-udk-cpu.yaml`, ap-south-1, CPU) serves
`https://15.252.103.69.sslip.io`. Every push to `main` redeploys it
(`.github/workflows/deploy.yml` -> `aws_deploy.py` -> `remote_deploy.sh` on the instance over SSM);
a push that changes none of the image's files restarts nothing. Run the same thing by hand with
`python deploy/aws_deploy.py`.

- **Config:** SSM SecureString `/sakhi/udk/config` holds the secrets and `UDK_DEVICE=cpu`. Every
  other setting comes from `.env.example` in the deployed commit, so detection settings ship with the code.
- **Intent model:** built in only once its HF read token is in SSM; without it the service runs with
  the intent gate off. Store it without it touching the terminal history or the repo:
  `read -rs T && aws ssm put-parameter --region ap-south-1 --name /sakhi/udk/hf-token --type SecureString --value "$T" --overwrite; unset T`
  then rerun the workflow (Actions -> Deploy to AWS -> Run workflow).
- **One-time setup:** stack `sakhi-udk-ci` (release bucket, the GitHub OIDC deploy role, the
  instance's read access to the token), separate so CI never updates `sakhi-udk` itself:
  ```
  aws cloudformation create-stack --region ap-south-1 --stack-name sakhi-udk-ci \
    --template-body file://deploy/sakhi-udk-ci.yaml --capabilities CAPABILITY_NAMED_IAM \
    --tags Key=Application,Value=Sakhi --parameters \
    ParameterKey=OidcProviderArn,ParameterValue=arn:aws:iam::494506753059:oidc-provider/token.actions.githubusercontent.com \
    ParameterKey=InstanceId,ParameterValue=i-09ae1cb17ed1e933b \
    ParameterKey=InstanceRoleName,ParameterValue=sakhi-udk-AppRole-3JMJUSbDNoEk
  ```
- A failed build leaves the running container untouched; a new container that never answers is
  replaced by the previous one. Live journeys drop during a swap (about a minute) and the website reconnects.

## GPU host: the full multilingual system (stack `sakhi-udk-gpu`)
English + custom UDK (own Whisper medium.en, in parallel) + Hindi + Telugu/Tamil/Kannada on one GPU, same image,
same pipeline as the CPU host. Measured (2026-10-07, Kaggle T4): ~1.5-1.9 s per speech segment, 0.21-0.23 s of work
per second of speech, 11.9 GB GPU / 5.4 GB RAM peak for one journey; decisions identical to CPU.
Which features run is a HOST setting (its SSM config); `remote_deploy.sh` never takes these from `.env.example`:
`UDK_DEVICE`, `UDK_CUSTOM_UDK_STT_MODEL`, `UDK_ENABLE_HINDI`, `UDK_ENABLE_INDIC_EXACT`, `UDK_HINDI_DEVICE`,
`UDK_TEXT_MODELS_DEVICE`, `UDK_CPU_THREADS`. So the CPU host (whose SSM sets none of the multilingual ones) is unchanged.

1. **Quota:** Service Quotas -> EC2 -> "Running On-Demand G and VT instances" >= 4 vCPU in ap-south-1.
2. **HF token** (already used for the intent model): `/sakhi/udk/hf-token` must read the private
   `sohans1092004/hindi-distress-frame` and `sohans1092004/udk-intent-mdeberta`, and have accepted the
   `ai4bharat/indic-conformer-600m-multilingual` terms. Without it a multilingual build stops with a message.
3. **Host config** `/sakhi/udk-gpu/config` (SecureString, docker --env-file format, no comments after values):
   ```
   UDK_SERVICE_TOKEN=<same as the website uses>
   UDK_WEBHOOK_URL=https://<website>/udk-alerts
   UDK_WEBHOOK_SECRET=<shared secret>
   UDK_DEVICE=cuda
   UDK_CUSTOM_UDK_STT_MODEL=medium.en
   UDK_ENABLE_HINDI=1
   UDK_ENABLE_INDIC_EXACT=te,ta,kn
   UDK_TEXT_MODELS_DEVICE=cpu
   HF_HUB_OFFLINE=1
   ```
   `HF_HUB_OFFLINE=1`: every model is in the image, so the service never calls Hugging Face at start (a missing
   one fails the start, and the deploy rolls back, instead of downloading). Store it without terminal history:
   `aws ssm put-parameter --region ap-south-1 --name /sakhi/udk-gpu/config --type SecureString --value file://gpu.env --overwrite && shred -u gpu.env`
4. **Stack** (check the AMI parameter resolves first:
   `aws ssm get-parameter --region ap-south-1 --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id`):
   ```
   aws cloudformation create-stack --region ap-south-1 --stack-name sakhi-udk-gpu \
     --template-body file://deploy/sakhi-udk-gpu.yaml --capabilities CAPABILITY_IAM \
     --tags Key=Application,Value=Sakhi --parameters \
     ParameterKey=VpcId,ParameterValue=<vpc> ParameterKey=SubnetId,ParameterValue=<public subnet>
   ```
   Its bootstrap checks the GPU is visible inside Docker (`nvidia-smi` in a container) and writes
   `/etc/udk/bootstrap-complete`; check that file over SSM before the first deploy.
5. **First deploy, by hand:** `UDK_APP_STACK=sakhi-udk-gpu python deploy/aws_deploy.py` (cold build ~30-45 min,
   ~25 GB image). Then `python deploy/smoke_test.py https://<EIP>.sslip.io <token> <an English, a Hindi and a Telugu clip>`
   and `docker logs udk 2>&1 | grep -iE "hindi|indic|intent gate|cuda"` over SSM.
6. **Deploy on every push to main** (switches CI from the CPU stack to this one):
   update stack `sakhi-udk-ci` with `AppStackName=sakhi-udk-gpu`, `InstanceId=<sakhi-udk-gpu InstanceId>`,
   `InstanceRoleName=<sakhi-udk-gpu InstanceRoleName>` (both are outputs of the GPU stack), then set the repository
   variable `UDK_APP_STACK=sakhi-udk-gpu` (Settings -> Secrets and variables -> Actions -> Variables).
   Unset it to go back to the CPU stack. Point the website at the GPU stack's Endpoint when the smoke test passes.
7. **Rollback:** a new container that never answers is replaced by the previous one, as on the CPU host. The
   multilingual switches can be turned off in `/sakhi/udk-gpu/config` and redeployed without a code change.

Limits that still apply (see the review answers): one worker per container, frames of all journeys share one
Parakeet and one gate worker, no drop policy when the GPU falls behind (one T4 keeps up with roughly 4-5 journeys
of continuous speech); a reconnect resumes from the last acked frame.

## Not in this image
Evaluation/test/Colab code, the distress detector (not validated yet),
non-English models, SepFormer separation, and `udk_endpoint.py` (clip upload service).
