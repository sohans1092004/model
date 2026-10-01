# Custom UDK Integration Guide

## Overview

Integrate per-user custom phrase detection into the existing pipeline.

**Files created:**
- `custom_udk.py` — enrollment & detection logic (from notebook)
- `custom_udk_api.py` — FastAPI endpoints (enrollment, list, delete)
- This guide

---

## 1. Add to API (api.py)

At the end of `api.py`, after the existing routes, add:

```python
import uuid
from custom_udk_api import register_custom_udk_routes

# ... existing FastAPI setup ...

# Register custom UDK routes
register_custom_udk_routes(app, db, stt_backend)
```

---

## 2. Add to Database (db.py)

Add three methods to `JourneyDB` class:

```python
def set_custom_udk(self, key: str, data: dict):
    """Store custom UDK profile + templates"""
    self.conn.execute(
        """INSERT OR REPLACE INTO custom_udks (key, data) VALUES (?, ?)""",
        (key, json.dumps(data))
    )
    self.conn.commit()

def list_custom_udks(self, user_id: str) -> list:
    """List all custom UDKs for a user"""
    rows = self.conn.execute(
        """SELECT data FROM custom_udks WHERE data LIKE ?""",
        (f'%"user_id": "{user_id}"%',)
    ).fetchall()
    return [json.loads(row[0]) for row in rows]

def get_custom_udk(self, key: str) -> dict:
    """Get a specific custom UDK"""
    row = self.conn.execute(
        """SELECT data FROM custom_udks WHERE key = ?""", (key,)
    ).fetchone()
    return json.loads(row[0]) if row else None

def delete_custom_udk(self, key: str):
    """Delete a custom UDK"""
    self.conn.execute("DELETE FROM custom_udks WHERE key = ?", (key,))
    self.conn.commit()
```

Also add the table in `__init__`:

```python
self.conn.execute("""
    CREATE TABLE IF NOT EXISTS custom_udks (
        key TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
```

---

## 3. Integrate into Detection (udk_engine.py)

In `UDKEngine.decide()`, after checking standard UDKs, add:

```python
def _check_custom_udks(self, transcript: str, audio_segment) -> dict:
    """Check if any custom UDK matches (speaker-dependent)"""
    if not hasattr(self, 'user_id') or not self.user_id:
        return {"detected": False, "layer": "custom_udk"}
    
    # Load user's enrolled custom UDKs
    from custom_udk_api import _decode_templates
    from db import JourneyDB
    
    db = JourneyDB()  # or pass as dependency
    udks = db.list_custom_udks(self.user_id)
    
    results = []
    for udk in udks:
        # Reconstruct profile
        prof = dict(udk["profile"])
        prof["tpls"] = _decode_templates(udk["templates_b64"])
        prof["ok"] = udk["profile"]["ok"]
        
        # Detect
        import custom_udk
        res = custom_udk.detect(audio_segment, transcript, prof)
        if res["detected"]:
            results.append({
                "phrase": prof["phrase"],
                "confidence": 1.0 if res["text_hit"] else 0.5,
                "text_hit": res["text_hit"],
                "audio_hit": res["audio_hit"]
            })
    
    if results:
        return {
            "detected": True,
            "layer": "custom_udk",
            "matches": results,
            "confidence": max(r["confidence"] for r in results)
        }
    
    return {"detected": False, "layer": "custom_udk"}
```

Then in `decide()`, after line checking standard UDKs:

```python
def decide(self, transcript, audio_segment, ...):
    # ... existing standard UDK checks ...
    
    # Check custom UDKs (speaker-dependent, no veto)
    custom = self._check_custom_udks(transcript, audio_segment)
    if custom["detected"]:
        # Custom UDK match = TRIGGER_ALL (always, no intent veto)
        return DecisionEvent(
            decision="TRIGGER_ALL",
            reason=f"custom_udk: {custom['matches'][0]['phrase']}",
            ...
        )
    
    # ... continue with existing logic ...
```

---

## 4. Usage Example

### Enroll:

```bash
# User uploads 4-6 clips saying their emergency phrase
curl -X POST http://localhost:8000/v1/users/alice123/custom-udks/enroll \
  -H "Authorization: Bearer token" \
  -F "files=@clip1.m4a" \
  -F "files=@clip2.m4a" \
  -F "files=@clip3.m4a" \
  -F "files=@clip4.m4a"

# Response:
{
  "udk_id": "3f2a1c9b-...",
  "phrase": "help me im trapped",
  "text_stability": 87.5,
  "ok": true,
  "status": "enrolled"
}
```

### Detect:

During a journey, on any incoming audio segment:
1. STT transcribes segment
2. Detection pipeline checks:
   - Standard UDKs (exact + fuzzy + semantic + KWS + scream)
   - **Custom UDKs (text match + audio DTW)**
3. If custom UDK matches → TRIGGER_ALL (no intent veto)

### List:

```bash
curl -X GET http://localhost:8000/v1/users/alice123/custom-udks \
  -H "Authorization: Bearer token"

# Response:
{
  "user_id": "alice123",
  "custom_udks": [
    {"udk_id": "3f2a1c9b-...", "phrase": "help me im trapped", "text_stability": 87.5},
    {"udk_id": "5e1d2f7a-...", "phrase": "call emergency services", "text_stability": 92.0}
  ]
}
```

### Delete:

```bash
curl -X DELETE http://localhost:8000/v1/users/alice123/custom-udks/3f2a1c9b-... \
  -H "Authorization: Bearer token"
```

---

## 5. Key Properties

| Feature | Behavior |
|---------|----------|
| Enrollment | 4-6 clips of user's voice saying the phrase |
| Decision | Text match (primary) + audio DTW (fallback) |
| Scope | Per-user (speaker-dependent) |
| Trigger | TRIGGER_ALL (no intent veto, unlike standard UDKs) |
| Storage | DB + encrypted templates |
| Rejection | <3 words, >40 chars, <80% stability |

---

## 6. Testing

```bash
cd ~/model_folder

# Test the module standalone
python -c "
import custom_udk
from faster_whisper import WhisperModel

whisper = WhisperModel('small.en')
raw = [custom_udk.load('clip1.m4a'), custom_udk.load('clip2.m4a')]
prof = custom_udk.build_profile(raw, [''] * len(raw), lambda y: 'hello world')
print('Profile:', prof)
"

# Run the full test
python test_on_prepped.py
```

---

## 7. Notes

- **Speaker-dependent**: Only the enrolled user's voice triggers the phrase
- **No intent veto**: Custom UDKs bypass the intent gate (always escalate)
- **Fallback audio matching**: If Whisper mishears, DTW on audio features catches it
- **Per-language support**: Works with any language Whisper supports
- **Limits**: Phrase must be 3–40 characters, ≥80% transcript stability from enrollment

---

## Files Summary

- `custom_udk.py` (260 lines) — Enrollment + detection logic
- `custom_udk_api.py` (120 lines) — FastAPI endpoints
- `api.py` (+10 lines) — Register routes
- `db.py` (+40 lines) — Storage methods
- `udk_engine.py` (+50 lines) — Detection integration

**Total: ~360 new lines of code**

Skipped: per-language model selection, async enrollment (user must wait for STT), duplicate phrase detection. Add when: multi-language support needed, enrollment should be async, phrase uniqueness required.
