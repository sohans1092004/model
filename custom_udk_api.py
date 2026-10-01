"""
API endpoints for per-user custom UDK enrollment & detection
Add these to api.py FastAPI app
"""
import os, tempfile
import numpy as np
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List
import json

import custom_udk
from db import JourneyDB
from stt import STTBackend


class CustomUDKEnrollRequest(BaseModel):
    """Enrollment metadata"""
    phrase: str = None  # optional; if provided, will be suggested to user


class CustomUDKProfile(BaseModel):
    """Enrolled phrase profile"""
    udk_id: str
    phrase: str
    text_stability: float
    ok: bool


class CustomUDKDetectResult(BaseModel):
    """Detection result"""
    detected: int
    text_hit: int
    audio_hit: int
    audio_score: float


# Storage: profiles stored in DB per user
# profiles[user_id][phrase_id] = {profile.json, templates.npz}

def register_custom_udk_routes(app: FastAPI, db: JourneyDB, stt_backend: STTBackend):
    """Register custom UDK endpoints on the app"""

    @app.post("/v1/users/{user_id}/custom-udks/enroll")
    async def enroll_custom_udk(
        user_id: str,
        files: List[UploadFile] = File(...),  # 4-6 audio clips
        require_service_token = Depends(None)  # add your auth here
    ):
        """
        Enroll a custom phrase for a user.

        Curl example:
        ```
        curl -X POST http://localhost:8000/v1/users/user123/custom-udks/enroll \
          -H "Authorization: Bearer token" \
          -F "files=@clip1.m4a" \
          -F "files=@clip2.m4a" \
          ... (4-6 total)
        ```
        """
        if not (4 <= len(files) <= 6):
            raise HTTPException(400, "Need 4-6 enrollment clips")

        # Load audio clips
        raw = []
        for f in files:
            try:
                content = await f.read()
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp.write(content)
                    tmp.flush()
                    y = custom_udk.load(tmp.name)
                    raw.append(y)
                os.unlink(tmp.name)
            except Exception as e:
                raise HTTPException(400, f"Failed to load {f.filename}: {str(e)}")

        if not raw:
            raise HTTPException(400, "No valid audio loaded")

        # Build profile (transcribe enrollment clips)
        prof = custom_udk.build_profile(raw, [""] * len(raw), stt_backend.transcribe)

        if not prof.get("ok"):
            raise HTTPException(
                400,
                f"Enrollment rejected: "
                f"phrase '{prof.get('phrase', '')}' "
                f"stability {prof.get('text_stability', 0):.0f}% "
                f"(need ≥3 words, ≤40 chars, ≥80% stability)"
            )

        # Store profile + templates in DB
        udk_id = str(uuid.uuid4())
        profile_data = custom_udk.profile_to_json(prof)
        templates = np.array(prof["tpls"])

        # Save to DB (example: JSON profile + npz templates as blobs)
        db_key = f"custom_udk_{user_id}_{udk_id}"
        db.set_custom_udk(db_key, {
            "user_id": user_id,
            "udk_id": udk_id,
            "profile": profile_data,
            "templates_b64": _encode_templates(templates)
        })

        return {
            "udk_id": udk_id,
            "phrase": profile_data["phrase"],
            "text_stability": profile_data["text_stability"],
            "ok": profile_data["ok"],
            "status": "enrolled"
        }

    @app.get("/v1/users/{user_id}/custom-udks")
    async def list_custom_udks(
        user_id: str,
        require_service_token = Depends(None)
    ):
        """List all enrolled custom UDKs for a user"""
        udks = db.list_custom_udks(user_id)
        return {
            "user_id": user_id,
            "custom_udks": [
                {
                    "udk_id": u["udk_id"],
                    "phrase": u["profile"]["phrase"],
                    "text_stability": u["profile"]["text_stability"]
                }
                for u in udks
            ]
        }

    @app.delete("/v1/users/{user_id}/custom-udks/{udk_id}")
    async def delete_custom_udk(
        user_id: str,
        udk_id: str,
        require_service_token = Depends(None)
    ):
        """Remove an enrolled custom UDK"""
        db_key = f"custom_udk_{user_id}_{udk_id}"
        db.delete_custom_udk(db_key)
        return {"status": "deleted", "udk_id": udk_id}


def _encode_templates(templates):
    """Encode numpy array to base64 for DB storage"""
    import base64
    import io
    buf = io.BytesIO()
    np.savez_compressed(buf, *templates)
    return base64.b64encode(buf.getvalue()).decode()


def _decode_templates(b64_str):
    """Decode templates from base64"""
    import base64
    import io
    buf = io.BytesIO(base64.b64decode(b64_str))
    arr = np.load(buf)
    return [arr[f"arr_{i}"] for i in range(len(arr.files))]
