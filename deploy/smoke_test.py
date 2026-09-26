"""Deploy smoke test: talks to a RUNNING service exactly like the website does -- start a
session, stream an audio file over the WebSocket in 0.5 s frames, stop, list the alerts.
    python deploy/smoke_test.py http://localhost:8000 <service token> clip1.mp3 [clip2.ogg ...]
Exits non-zero if the service refuses a step, so a broken deployment can't look fine.
"""
import json
import struct
import sys
import time
import urllib.request

import numpy as np
try:
    from faster_whisper import decode_audio  # in the image and on Colab
except ImportError:  # a laptop without it
    def decode_audio(path, sampling_rate):
        import librosa
        return librosa.load(path, sr=sampling_rate, mono=True)[0]
from websockets.sync.client import connect

FRAME_HEADER = struct.Struct(">Qd")  # as api.py: seq uint64, client_ts float64
FRAME_BYTES = 16000  # 0.5 s of 16 kHz int16 mono


def call(base, token, method, path, body=None):
    req = urllib.request.Request(base + path, method=method, headers={"X-Service-Token": token, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def run(base, token, path):
    audio = decode_audio(path, sampling_rate=16000)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes() + b"\x00" * 64000  # + 2 s silence to close the last utterance
    start = call(base, token, "POST", "/v1/journeys/start", {"user_id": "smoke-test"})
    jid = start["journey_id"]
    ws_url = base.replace("http", "ws", 1) + f"{start['stream_endpoint']}?session_token={start['session_token']}"
    live, t0 = [], time.time()
    with connect(ws_url) as ws:
        for seq, i in enumerate(range(0, len(pcm), FRAME_BYTES)):
            ws.send(FRAME_HEADER.pack(seq, time.time()) + pcm[i:i + FRAME_BYTES])
            while True:  # read until this frame's ack; events arrive right after an ack
                msg = json.loads(ws.recv(timeout=120))
                if msg["type"] == "event":
                    live.append(msg)
                elif msg["type"] == "ack" and msg["ack_seq"] >= seq:
                    break
    call(base, token, "POST", f"/v1/journeys/{jid}/stop", {"reason": "smoke_test"})
    events = call(base, token, "GET", f"/v1/journeys/{jid}/events?include_vetoed=true")["events"]
    print(f"\n{path}  ({len(audio) / 16000:.1f} s audio, processed in {time.time() - t0:.1f} s)")
    print(f"  {len(live)} alert(s) on the stream, {len(events)} in the session record (incl. intent-gate vetoes)")
    for e in events:
        print(f"  {e['decision']:<15} {e['udk_id'] or '(scream)':<9} {e['layer']:<18} conf {e['confidence']:.2f}  {e['transcript'][:70]!r}")
        if e.get("reason"):
            print(f"  {'':<15} why: {e['reason']}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    base, token = sys.argv[1].rstrip("/"), sys.argv[2]
    for f in sys.argv[3:]:
        run(base, token, f)
