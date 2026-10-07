"""Deploys this checkout to the live UDK service (CloudFormation stack sakhi-udk, or the GPU stack
sakhi-udk-gpu with UDK_APP_STACK=sakhi-udk-gpu), locally or from .github/workflows/deploy.yml:
    python deploy/aws_deploy.py
Uploads exactly the image's files (Dockerfile.dockerignore) to the sakhi-udk-ci release
bucket; over SSM the instance fetches them and runs deploy/remote_deploy.sh, which builds,
swaps the container and rolls back if the new one never answers. Needs only the AWS CLI."""
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_package import ROOT, whitelist  # noqa: E402

ACCOUNT, REGION = "494506753059", "ap-south-1"
APP_STACK, CI_STACK = os.environ.get("UDK_APP_STACK") or "sakhi-udk", "sakhi-udk-ci"
# Not in the image, but the instance needs them to build and run it.
DEPLOY_FILES = ["deploy/Dockerfile", "deploy/Dockerfile.dockerignore", "deploy/.env.example", "deploy/remote_deploy.sh"]


def aws(*args: str) -> dict:
    return json.loads(subprocess.check_output(["aws", *args, "--region", REGION, "--output", "json"]))


def outputs(stack: str) -> dict:
    return {o["OutputKey"]: o["OutputValue"]
            for o in aws("cloudformation", "describe-stacks", "--stack-name", stack)["Stacks"][0]["Outputs"]}


def main() -> None:
    if aws("sts", "get-caller-identity")["Account"] != ACCOUNT:
        raise SystemExit("refusing: these credentials are not for the Sakhi AWS account")
    app, ci = outputs(APP_STACK), outputs(CI_STACK)
    instance = app["InstanceId"]

    files = sorted(set(whitelist()) | {ROOT / f for f in DEPLOY_FILES})
    # Named by content, not by commit: a push that changes none of these files maps to a
    # release the instance already runs, so it rebuilds and restarts nothing.
    digest = hashlib.sha256()
    for f in files:
        digest.update(f.relative_to(ROOT).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    release = digest.hexdigest()[:16]

    key = f"s3://{ci['ReleaseBucket']}/releases/{release}.tgz"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "release.tgz"
        with tarfile.open(archive, "w:gz") as tar:
            for f in files:
                tar.add(f, arcname=f.relative_to(ROOT).as_posix())
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        subprocess.run(["aws", "s3", "cp", str(archive), key, "--region", REGION, "--only-show-errors"], check=True)
    # The instance role has no S3 access; a 15-minute link is all it gets.
    url = subprocess.check_output(["aws", "s3", "presign", key, "--expires-in", "900", "--region", REGION], text=True).strip()

    target, tgz = f"/srv/udk/releases/{release}", f"/tmp/udk-{release}.tgz"
    script = "\n".join([
        "set -eu",
        f"rm -rf {target} && mkdir -p {target}",
        f"curl -fsS -o {tgz} '{url}'",
        f"echo '{sha}  {tgz}' | sha256sum -c --status",
        f"tar -xzf {tgz} -C {target} --no-same-owner && rm {tgz}",
        "ls -1dt /srv/udk/releases/* | tail -n +4 | xargs -r rm -rf",  # keep the last 3
        f"bash {target}/deploy/remote_deploy.sh {release} {REGION}",
    ])
    command = aws("ssm", "send-command", "--instance-ids", instance, "--document-name", "AWS-RunShellScript",
                  "--comment", f"udk deploy {release}",
                  "--parameters", json.dumps({"commands": [script], "executionTimeout": ["5400"]}))["Command"]["CommandId"]
    print(f"release {release}: SSM command {command} on {instance}", flush=True)

    # Wait for the result, so a failed build fails this run instead of passing as "sent".
    status, invocation = "Pending", {}
    while status in ("Pending", "InProgress", "Delayed"):
        time.sleep(20)
        try:
            invocation = aws("ssm", "get-command-invocation", "--command-id", command, "--instance-id", instance)
        except subprocess.CalledProcessError:
            continue  # not queryable for a moment after send-command
        status = invocation["Status"]
    print(invocation.get("StandardOutputContent", "")[-4000:])
    print(invocation.get("StandardErrorContent", "")[-4000:], file=sys.stderr)
    if status != "Success":
        raise SystemExit(f"deploy finished as {status}")

    # Through Caddy and TLS, as the website reaches it.
    with urllib.request.urlopen(app["Endpoint"] + "/openapi.json", timeout=15) as r:
        assert r.status == 200, r.status
    print(f"live: {app['Endpoint']}")


if __name__ == "__main__":
    main()
