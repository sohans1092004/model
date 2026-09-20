"""
M3: streaming API (Section 9). REST for journey lifecycle (start/stop/
status/events); WebSocket for audio ingestion.

Section 9's default recommendation is gRPC bidi streaming, falling back
to WebSocket "if [the client stack] doesn't [already use gRPC] and you
want broader client support." This prototype has no existing app stack to
match and no reason to take on a protobuf/codegen toolchain to prove
streaming ingestion works, so WebSocket is the pragmatic choice here --
swapping the transport for gRPC later wouldn't change anything below the
ingestion boundary (JourneyState / pipeline processing stays the same).

ponytail: incremental detection re-scans the whole contiguous audio
buffer on every frame rather than using a truly stateful streaming VAD --
fine at prototype/test scale (buffers are seconds, not hours); upgrade to
real incremental VAD state if per-frame buffer size becomes the
bottleneck.

M5: journey metadata + events are now durable via db.py (SQLite standing
in for Postgres) alongside AudioStore -- a restart recovers the whole
journey (session_token, personal UDK, status), not just its audio.

M6 (Section 10): audio and sensitive DB columns are encrypted at rest via
crypto.py; /start requires a scoped service credential and is rate
limited (the testable half of "mTLS or a scoped service token" -- real
mTLS needs real certs, out of scope here); audio playback goes through a
short-lived signed URL with an ownership check, audited on every access.

M7 (Section 11): the metrics/SLO set is tracked via metrics.py and
exposed at GET /metrics. JourneyStore.evict_finished() frees a completed
journey's in-memory state once it's safely durable elsewhere (M5) --
without it, a long-running process's memory grows with total journeys
ever handled, not concurrent ones, which is exactly the kind of leak a
soak test exists to catch (Section 12). Autoscaling and edge KWS
deployment are named in README.md as blocked on real infra/an earlier
deferred decision, not built here -- see that section before assuming
either exists.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import struct
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from audit import AuditLog
from crypto import KeyManager
from db import JourneyDB
from enrollment import enroll
from event_delivery import EventDeliveryQueue
from kws import KWSBackend
from semantic import SemanticBackend
from separation import SeparatorBackend
from metrics import Metrics
from stt import MockSTT, STTBackend
from storage import AudioStore
from udk_engine import DecisionEvent, UDKEngine
from udks import SAMPLE_PERSONAL_UDK, SUPPORTED_LANGUAGES, UDK, all_udks
from vad import VAD

HEARTBEAT_INTERVAL_S = 7
HEARTBEAT_GRACE_S = 20  # missed-heartbeat grace window (Section 3)
# Tighter grace once a UDK has already fired for this journey: going dark
# right after a safety trigger is itself a signal worth reacting to
# faster than ordinary end-of-journey silence, not the same case.
POST_TRIGGER_HEARTBEAT_GRACE_S = 10
FRAME_HEADER = struct.Struct(">Qd")  # seq: uint64, client_ts: float64
PROCESSING_VERSION = "pipeline-2026.09"  # bump when VAD/STT/matching logic changes meaningfully
AUDIO_TOKEN_TTL_S = 300  # Section 10: "short-lived signed URL, never a permanent public object path"

# Section 9: "the existing app authenticates as a service (mTLS or a
# scoped service token)". The env var is how a real deployment sets this;
# the fallback is a dev-only placeholder, loudly named so it's obvious if
# it ever ends up live somewhere it shouldn't.
DEV_SERVICE_TOKEN = "dev-service-token-CHANGE-ME"
_SERVICE_TOKEN = os.environ.get("UDK_SERVICE_TOKEN", DEV_SERVICE_TOKEN)

JourneyStatus = Literal["ACTIVE", "FINALIZING", "COMPLETE", "TIMED_OUT", "TIMED_OUT_AFTER_TRIGGER"]


@dataclass
class JourneyState:
    journey_id: str
    user_id: str
    session_token: str
    engine: UDKEngine
    stt: STTBackend
    personal_udk: UDK
    status: JourneyStatus = "ACTIVE"
    started_at: float = field(default_factory=time.time)
    last_heartbeat_at: float = field(default_factory=time.time)
    next_expected_seq: int = 0
    pending_frames: dict[int, bytes] = field(default_factory=dict)
    audio_buffer: bytearray = field(default_factory=bytearray)
    processed_up_to_ms: int = 0
    vad: VAD = field(default_factory=VAD)
    events: list[dict] = field(default_factory=list)
    kws: KWSBackend | None = None  # Section 4's Approach E; None = KWS disabled for this journey
    had_trigger: bool = False  # any TRIGGER_VERIFY/TRIGGER_ALL ever fired -- tightens the timeout grace
    language: str = "en"  # which UDK phrase list/semantic matcher this journey uses -- see udks.py


class JourneyStore:
    """In-memory registry, backed by db.py for anything that needs to
    survive a restart (Section 14's M5)."""

    def __init__(self, db: JourneyDB | None = None):
        self._journeys: dict[str, JourneyState] = {}
        self._db = db

    def get(self, journey_id: str) -> JourneyState | None:
        journey = self._journeys.get(journey_id)
        if journey and journey.status == "ACTIVE":
            self._check_timeout(journey)
        return journey

    def create_or_get(
        self,
        journey_id: str,
        user_id: str,
        stt: STTBackend,
        personal_udk,
        audio_store: AudioStore | None = None,
        kws: KWSBackend | None = None,
        semantic_matcher: SemanticBackend | None = None,
        language: str = "en",
        multilingual_semantic_matcher: SemanticBackend | None = None,
        stt_by_language: dict[str, STTBackend] | None = None,
        kws_by_language: dict[str, KWSBackend] | None = None,
    ) -> tuple[JourneyState, bool]:
        """Idempotent on journey_id (Section 9): a retried start for an
        existing journey returns it rather than creating a duplicate.

        If this journey isn't in memory, check durable storage before
        assuming it's brand new (a process restart -- this in-memory
        dict is wiped, disk/DB aren't):
          - self._db has the journey's session_token, status, and
            enrolled personal UDK -- a full recovery, not just audio
            (this is what M5 adds over M4, which could only recover the
            audio itself).
          - audio_store rebuilds the live buffer/next_expected_seq from
            whatever's durably stored (Section 6: resume without
            reprocessing everything or skipping segments).
        A genuinely new journey_id (not in memory or DB) gets a fresh
        session_token and is persisted immediately."""
        existing = self._journeys.get(journey_id)
        if existing is not None:
            return existing, False

        recovered = self._db.load_journey(journey_id) if self._db is not None else None
        if recovered is not None:
            # Language comes from the DB record, not this call's `language`
            # param -- a reconnecting/retried request after a crash may not
            # (and shouldn't need to) resend it, same reasoning as
            # personal_udk being recovered from storage rather than trusted
            # from the caller.
            journey_language = recovered.get("language", "en")
            matcher = semantic_matcher if journey_language == "en" else multilingual_semantic_matcher
            journey_stt = (stt_by_language or {}).get(journey_language, stt)
            journey_kws = (kws_by_language or {}).get(journey_language, kws)
            personal_udk = UDK(
                udk_id=recovered["personal_udk_id"],
                phrase=recovered["personal_udk_phrase"],
                udk_type="PERSONAL",
                verify_by_default=bool(recovered["personal_udk_verify_by_default"]),
            )
            journey = JourneyState(
                journey_id=journey_id,
                user_id=recovered["user_id"],
                session_token=recovered["session_token"],
                engine=UDKEngine(all_udks(personal_udk, language=journey_language), semantic_matcher=matcher),
                stt=journey_stt,
                personal_udk=personal_udk,
                status=recovered["status"],
                started_at=recovered["started_at"],
                last_heartbeat_at=recovered["last_heartbeat_at"],
                kws=journey_kws,
                had_trigger=bool(recovered.get("had_trigger", False)),
                language=journey_language,
            )
        else:
            matcher = semantic_matcher if language == "en" else multilingual_semantic_matcher
            journey_stt = (stt_by_language or {}).get(language, stt)
            journey_kws = (kws_by_language or {}).get(language, kws)
            journey = JourneyState(
                journey_id=journey_id,
                user_id=user_id,
                session_token=secrets.token_urlsafe(24),
                engine=UDKEngine(all_udks(personal_udk, language=language), semantic_matcher=matcher),
                stt=journey_stt,
                personal_udk=personal_udk,
                kws=journey_kws,
                language=language,
            )

        if audio_store is not None:
            # AudioStore is authoritative for buffer state specifically --
            # it's derived from what's actually on disk, not a cached
            # count that could drift from it.
            buffer, next_seq = audio_store.read_contiguous_prefix(journey_id)
            journey.audio_buffer.extend(buffer)
            journey.next_expected_seq = next_seq

        if self._db is not None:
            self._db.save_journey(journey)

        self._journeys[journey_id] = journey
        if recovered is None:
            _metrics.journey_started()
        return journey, True

    def _check_timeout(self, journey: JourneyState) -> None:
        """Section 3: no heartbeat for N seconds -> auto-finalize rather
        than leaving the journey ACTIVE forever. Checked lazily on access
        instead of an active background sweep -- a production deployment
        would want the sweep so an unaccessed journey still finalizes
        promptly, but that's more machinery than a prototype needs.

        Going dark AFTER a UDK already fired is a materially different
        situation from ordinary end-of-journey silence -- shorter grace
        window, and a status distinct from plain TIMED_OUT so the
        downstream platform can tell "session ended" from "went dark
        right when it mattered" and react accordingly (escalate rather
        than wait), without this system deciding what that reaction is
        (Section 7a: this system decides, it doesn't dispatch)."""
        grace = POST_TRIGGER_HEARTBEAT_GRACE_S if journey.had_trigger else HEARTBEAT_GRACE_S
        if time.time() - journey.last_heartbeat_at > grace:
            journey.status = "TIMED_OUT_AFTER_TRIGGER" if journey.had_trigger else "TIMED_OUT"
            _metrics.journey_timed_out(after_trigger=journey.had_trigger)
            if self._db is not None:
                self._db.save_journey(journey)

    def evict_finished(self, older_than_s: float) -> list[str]:
        """M7/Section 12: frees a finished journey's in-memory state
        (audio buffer, VAD/STT/engine objects) a while after it's done --
        safe since M5 made GET endpoints fall back to durable storage for
        anything not live in memory. Without this, a long-running
        process's memory grows with total journeys ever handled, not
        concurrent ones -- exactly the leak a soak test is meant to catch.
        A sweep function, not a scheduler, same as retention.py's sweep()."""
        now = time.time()
        to_evict = [
            jid
            for jid, j in self._journeys.items()
            if j.status in ("COMPLETE", "TIMED_OUT") and now - j.last_heartbeat_at > older_than_s
        ]
        for jid in to_evict:
            del self._journeys[jid]
        return to_evict


def _decision_to_event(journey: JourneyState, decision: DecisionEvent, seg) -> dict:
    """Section 9's full decision-event schema. `location` is honestly
    always null -- this prototype never built a location-ingestion
    mechanism (nobody asked for one, and Section 1 treats it as
    optional/best-effort metadata anyway). `model_version.kws` reflects
    whichever KWS backend (if any) is enabled for this journey."""
    udk_id = decision.udk.udk_id if decision.udk else "none"
    event_id = hashlib.sha256(f"{journey.journey_id}:{seg.start_ms}:{udk_id}".encode()).hexdigest()[:16]
    return {
        "event_id": event_id,
        "journey_id": journey.journey_id,
        "user_id": journey.user_id,
        "decision": decision.decision,
        "udk_id": decision.udk.udk_id if decision.udk else None,
        "udk_type": decision.udk.udk_type if decision.udk else None,
        "confidence": round(decision.confidence, 3),
        # The audio's actual time (journey start + offset into the
        # stream), not when the server happened to process it -- matters
        # for ordering a delayed/backlog detection correctly (Section 9).
        "timestamp": journey.started_at + seg.start_ms / 1000.0,
        "server_received_ts": time.time(),
        "transcript": decision.transcript,
        "audio_segment_id": f"{journey.journey_id}:{seg.start_ms}-{seg.end_ms}",
        "location": None,
        "processing_version": PROCESSING_VERSION,
        "model_version": {
            "vad": "webrtcvad",
            "stt": journey.stt.model_version,
            "kws": journey.kws.model_version if journey.kws is not None else None,
        },
    }


def _run_incremental_detection(journey: JourneyState, final: bool = False) -> list[dict]:
    pcm = bytes(journey.audio_buffer)
    segments = journey.vad.segment_speech(pcm)
    if not segments:
        return []

    if final:
        finalizable = segments
    else:
        # A segment is safe to finalize once more buffered audio has
        # arrived after its end -- proof it already got its full
        # post-roll and isn't still extending (Section 2: don't cut
        # mid-speech). This replaces an earlier "exclude only the list's
        # last segment" rule, which never finalized a single continuous
        # utterance with nothing spoken after it (that segment is always
        # last) -- found while testing the real end-to-end latency path.
        total = journey.vad.total_ms(pcm)
        finalizable = [seg for seg in segments if seg.end_ms < total]

    new_events = []
    for seg in finalizable:
        if seg.end_ms <= journey.processed_up_to_ms:
            continue
        journey.processed_up_to_ms = seg.end_ms
        stt_start = time.monotonic()
        transcript = journey.stt.transcribe(seg.pcm)
        _metrics.stt_latency(time.monotonic() - stt_start)
        kws_match = journey.kws.spot(seg.pcm) if journey.kws is not None else None
        # Deciding even on an empty transcript is what lets KWS fire on
        # its own when STT gets nothing (Section 3's STT-outage row) --
        # skipping early here would silently defeat the entire point of
        # running KWS in parallel (Section 4's Approach E).
        if not transcript.text and kws_match is None:
            continue
        decision = journey.engine.decide(transcript.text, now_s=time.monotonic(), kws_match=kws_match)
        if decision.decision == "NO_ACTION":
            # Speech-separation fallback (separation.py): only tried once
            # the primary pass has already missed, and only when opted in
            # -- real measured cost (new FP path + ~4-8s CPU latency) means
            # this must never run on every segment. See separation.py's
            # module docstring for the real recovered-recall numbers.
            if _separator is not None:
                from separation import retry_with_separation

                recovered = retry_with_separation(
                    seg.pcm, journey.stt, journey.engine, _separator, time.monotonic(), kws=journey.kws
                )
                if recovered is not None:
                    decision = recovered
            if decision.decision == "NO_ACTION":
                continue
        event = _decision_to_event(journey, decision, seg)
        journey.events.append(event)
        new_events.append(event)
        journey.had_trigger = True  # tightens the heartbeat grace from here on (_check_timeout)
        _metrics.detection(
            event["decision"], event["confidence"], event["server_received_ts"] - event["timestamp"]
        )

        # Durable, queryable record (Section 9: "the platform can always
        # reconcile its state... after any gap") -- survives a restart
        # even if the in-memory journey.events list doesn't.
        _db.save_event(event)

        # Durable outbound queue before attempting delivery (Section 6's
        # Event Engine): a crash between "detected" and "delivered"
        # doesn't drop the alert, and the deterministic event_id means a
        # retried delivery downstream doesn't double-alert.
        _event_queue.enqueue(event)
        if _downstream_deliver(event):
            _event_queue.mark_delivered(event["event_id"])
            _metrics.event_delivered()
        else:
            _metrics.event_delivery_failed()
    return new_events


def _ingest_frame(journey: JourneyState, seq: int, pcm: bytes, audio_store: AudioStore) -> list[dict]:
    # Idempotent: a retried/duplicate frame for an already-consumed seq
    # (Section 3: client retries after a lost ack) is a no-op here, not a
    # re-write or a stale pending_frames entry that never gets cleaned up.
    audio_store.write_segment(journey.journey_id, seq, pcm)  # durability before processing (Section 6)
    _metrics.chunk_received()
    if seq < journey.next_expected_seq:
        return []

    if seq > journey.next_expected_seq:
        _metrics.sequence_gap_detected()  # Section 11: gap dashboard/alert signal

    journey.pending_frames[seq] = pcm
    while journey.next_expected_seq in journey.pending_frames:
        journey.audio_buffer.extend(journey.pending_frames.pop(journey.next_expected_seq))
        journey.next_expected_seq += 1

    return _run_incremental_detection(journey)


class RateLimiter:
    """Fixed-window limiter, one window per key (Section 10: "journey
    creation rate-limited per service credential"). ponytail: naive
    fixed-window counting, not sliding-window/token-bucket, and one
    process's in-memory dict, not shared state across instances -- fine
    for a prototype demonstrating the mechanism exists; a real deployment
    would rate-limit at the gateway with shared state."""

    def __init__(self, max_requests: int, window_s: float):
        self.max_requests = max_requests
        self.window_s = window_s
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start > self.window_s:
                window_start, count = now, 0
            count += 1
            self._windows[key] = (window_start, count)
            return count <= self.max_requests


def _sign_audio_token(journey_id: str, expires_at: float) -> str:
    sig = hmac.new(_signing_secret, f"{journey_id}:{expires_at}".encode(), hashlib.sha256).hexdigest()
    return f"{expires_at}.{sig}"


def _verify_audio_token(journey_id: str, token: str) -> bool:
    try:
        # rsplit, not split: expires_at is a float whose own repr
        # contains a "." (e.g. "1789818821.947...") -- splitting from the
        # left would cut the timestamp in half. The hex signature itself
        # never contains a dot, so splitting from the right is safe.
        expires_str, sig = token.rsplit(".", 1)
        expires_at = float(expires_str)
    except (ValueError, AttributeError):
        return False
    if time.time() > expires_at:
        return False
    expected = hmac.new(_signing_secret, f"{journey_id}:{expires_at}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def _journey_owner(journey_id: str) -> str | None:
    journey = _store.get(journey_id)
    if journey is not None:
        return journey.user_id
    row = _db.load_journey(journey_id)
    return row["user_id"] if row is not None else None


def require_service_token(x_service_token: str = Header(...)) -> None:
    """Section 9's scoped-service-token half of "mTLS or a scoped service
    token" -- real mTLS needs real certs/infra out of scope here, this is
    the testable part. Also enforces the per-credential rate limit
    (Section 10) since both gate the same entry point."""
    if not secrets.compare_digest(x_service_token, _SERVICE_TOKEN):
        raise HTTPException(401, "invalid service credential")
    if not _rate_limiter.allow(x_service_token):
        raise HTTPException(429, "rate limit exceeded")


def _load_or_create_signing_secret(path: Path) -> bytes:
    if path.exists():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_bytes(32)
    path.write_bytes(secret)
    return secret


def _load_kws_backend(references_path: Path) -> KWSBackend | None:
    """KWS stays fully optional and off by default (Section 4's Approach
    E is additive, not required) -- explicit opt-in via UDK_ENABLE_KWS,
    not just "the reference file happens to exist." Loading torch +
    wav2vec2 takes 10+ seconds and adds real per-segment inference cost;
    every prior milestone's tests import this module and go through
    /start, and none of them should silently get 10x slower or start
    running real model inference against synthetic test PCM just because
    enroll_kws_references.py was run once in this checkout. A real
    deployment sets the env var; nothing else changes by default."""
    if os.environ.get("UDK_ENABLE_KWS") != "1" or not references_path.exists():
        return None
    try:
        from kws import Wav2Vec2DTWSpotter

        spotter = Wav2Vec2DTWSpotter()
        spotter.load_references(references_path)
        return spotter
    except Exception:
        return None


def _load_indic_kws_backends() -> dict[str, KWSBackend]:
    """Same opt-in reasoning as _load_kws_backend, but its own separate
    env var (UDK_ENABLE_INDIC_KWS=1, distinct from UDK_ENABLE_KWS and
    UDK_ENABLE_INDIC_STT) since this is a real, separate multi-GB-scale
    model set (kws.py's INDIC_KWS_MODELS -- Vakyansh's per-language
    ASR-fine-tuned wav2vec2 models, NOT the same models/thresholds as
    English's KWS). Requires enroll_indic_kws_references.py to have been
    run first (produces kws_references_<lang>.npz per language) --
    languages without that file are silently skipped, same fallback
    philosophy as every other _load_* function in this file."""
    if os.environ.get("UDK_ENABLE_INDIC_KWS") != "1":
        return {}
    backends: dict[str, KWSBackend] = {}
    try:
        from kws import INDIC_KWS_MODELS, INDIC_KWS_THRESHOLDS, Wav2Vec2DTWSpotter

        for lang, model_name in INDIC_KWS_MODELS.items():
            references_path = Path(__file__).parent / f"kws_references_{lang}.npz"
            if not references_path.exists():
                continue
            try:
                spotter = Wav2Vec2DTWSpotter(model_name=model_name, match_threshold=INDIC_KWS_THRESHOLDS[lang])
                spotter.load_references(references_path)
                backends[lang] = spotter
            except Exception:
                pass
    except Exception:
        pass
    return backends


def _load_semantic_matcher() -> SemanticBackend | None:
    """Same reasoning and same opt-in pattern as _load_kws_backend: real
    semantic matching (sentence-transformers) is additive, not required
    (udk_engine.py falls back to the rapidfuzz stub with no semantic_matcher
    given), and loading it costs real seconds + a real model download --
    none of M1-M7's existing tests should pay that just because torch
    happens to be installed for KWS."""
    if os.environ.get("UDK_ENABLE_SEMANTIC") != "1":
        return None
    try:
        from semantic import SentenceTransformerSemanticMatcher

        return SentenceTransformerSemanticMatcher()
    except Exception:
        return None


def _load_multilingual_semantic_matcher() -> SemanticBackend | None:
    """Same opt-in pattern (UDK_ENABLE_SEMANTIC=1) as _load_semantic_matcher,
    but for the other four languages (SUPPORTED_LANGUAGES minus "en") --
    a SEPARATE model/threshold (LaBSE/0.80), not the English one's model/
    threshold (paraphrase-multilingual-MiniLM-L12-v2/0.55), because real
    testing found that model doesn't meaningfully discriminate meaning in
    Telugu/Kannada/Tamil at all -- see semantic.py's module docstring for
    the real calibration data behind both models' choices."""
    if os.environ.get("UDK_ENABLE_SEMANTIC") != "1":
        return None
    try:
        from semantic import (
            MULTILINGUAL_FUZZY_THRESHOLD,
            MULTILINGUAL_MODEL,
            MULTILINGUAL_THRESHOLD,
            SentenceTransformerSemanticMatcher,
        )

        return SentenceTransformerSemanticMatcher(
            model_name=MULTILINGUAL_MODEL, threshold=MULTILINGUAL_THRESHOLD, fuzzy_threshold=MULTILINGUAL_FUZZY_THRESHOLD
        )
    except Exception:
        return None


def _load_indic_stt_backends() -> dict[str, STTBackend]:
    """Opt-in via UDK_ENABLE_INDIC_STT=1 (separate from UDK_ENABLE_SEMANTIC
    -- this loads real language-specific Whisper checkpoints, a real
    multi-GB-scale download+load cost per language, distinct from and
    additive to semantic matching). All four non-English languages now
    have real measured evidence for their fine-tune outperforming the
    generic multilingual model (see stt.py's IndicFineTunedWhisperSTT and
    README.md): Telugu 100%, Tamil 100%, Kannada 95%, Hindi 95%, vs. the
    generic model's 5%/90%/45%/90% respectively."""
    if os.environ.get("UDK_ENABLE_INDIC_STT") != "1":
        return {}
    backends: dict[str, STTBackend] = {}
    try:
        from stt import IndicFineTunedWhisperSTT

        for lang in ("te", "kn", "hi", "ta"):
            try:
                backends[lang] = IndicFineTunedWhisperSTT(lang)
            except Exception:
                pass
    except Exception:
        pass
    return backends


def _load_separator() -> SeparatorBackend | None:
    """Same opt-in pattern as KWS/semantic: real speech separation
    (speechbrain's pretrained SepFormer) is additive, and only ever
    invoked as a NO_ACTION fallback (see separation.py) -- torch +
    speechbrain shouldn't cost every existing test a startup penalty
    just because UDK_ENABLE_KWS/SEMANTIC happen to already need torch."""
    if os.environ.get("UDK_ENABLE_SEPARATION") != "1":
        return None
    try:
        from separation import SepformerSeparator

        return SepformerSeparator()
    except Exception:
        return None


def _load_db(key_manager, fallback_path):
    """Real Postgres if UDK_DATABASE_URL is set (see db_postgres.py),
    else the local SQLite stand-in (db.py) -- same opt-in-by-env-var
    pattern as KWS/semantic. Falls back to SQLite on any connection
    failure rather than refusing to start; a real deployment that sets
    the URL should fix a broken database, not have this silently paper
    over it forever, so this is a startup-time fallback, not a retry loop."""
    url = os.environ.get("UDK_DATABASE_URL")
    if url:
        try:
            from db_postgres import PostgresJourneyDB

            return PostgresJourneyDB(url, key_manager=key_manager)
        except Exception:
            pass
    return JourneyDB(fallback_path, key_manager=key_manager)


def _load_audio_store(key_manager, fallback_path):
    """Real S3-compatible storage if UDK_S3_ENDPOINT + UDK_S3_BUCKET are
    set (see storage_s3.py), else the local filesystem stand-in
    (storage.py) -- same pattern as _load_db."""
    endpoint = os.environ.get("UDK_S3_ENDPOINT")
    bucket = os.environ.get("UDK_S3_BUCKET")
    if endpoint and bucket:
        try:
            from storage_s3 import S3AudioStore

            return S3AudioStore(
                bucket=bucket,
                endpoint_url=endpoint,
                access_key=os.environ.get("UDK_S3_ACCESS_KEY", ""),
                secret_key=os.environ.get("UDK_S3_SECRET_KEY", ""),
                key_manager=key_manager,
            )
        except Exception:
            pass
    return AudioStore(fallback_path, key_manager=key_manager)


def _load_downstream_deliver() -> Callable[[dict], bool]:
    """Real Kafka publish if UDK_KAFKA_BOOTSTRAP_SERVERS + UDK_KAFKA_TOPIC
    are set (see kafka_delivery.py), else the stub -- "the real safety
    platform isn't built here" now has a real half: publishing to a real
    bus is buildable, the platform consuming from it still isn't ours."""
    bootstrap = os.environ.get("UDK_KAFKA_BOOTSTRAP_SERVERS")
    topic = os.environ.get("UDK_KAFKA_TOPIC")
    if bootstrap and topic:
        try:
            from kafka_delivery import make_kafka_deliver

            return make_kafka_deliver(bootstrap, topic)
        except Exception:
            pass
    return lambda event: True


# Module-level, swapped out wholesale in tests (api._stt_backend = ...,
# api._audio_store = ...) -- no DI framework needed for a prototype this
# size (M1/M2 make the same call).
_tmp = Path(tempfile.gettempdir())
_stt_backend: STTBackend = MockSTT()
# Separate key material for audio vs. general DB secrets (Section 10).
_audio_key_manager = KeyManager(_tmp / "udk_audio.key")
_db_key_manager = KeyManager(_tmp / "udk_db.key")
_audio_store = _load_audio_store(_audio_key_manager, _tmp / "udk_journey_audio")
_event_queue = EventDeliveryQueue(_tmp / "udk_event_queue")
_db = _load_db(_db_key_manager, _tmp / "udk_journeys.sqlite3")
_audit_log = AuditLog(_tmp / "udk_audit_log.sqlite3")
_rate_limiter = RateLimiter(max_requests=10, window_s=60)
_signing_secret = _load_or_create_signing_secret(_tmp / "udk_signing_secret.bin")
_metrics = Metrics()
_downstream_deliver: Callable[[dict], bool] = _load_downstream_deliver()
_store = JourneyStore(db=_db)
# None unless enroll_kws_references.py has been run -- see _load_kws_backend.
_kws_backend: KWSBackend | None = _load_kws_backend(Path(__file__).parent / "kws_references.npz")
# None unless UDK_ENABLE_SEMANTIC=1 -- see _load_semantic_matcher.
_semantic_matcher: SemanticBackend | None = _load_semantic_matcher()
# None unless UDK_ENABLE_SEMANTIC=1 -- see _load_multilingual_semantic_matcher.
_multilingual_semantic_matcher: SemanticBackend | None = _load_multilingual_semantic_matcher()
# {} unless UDK_ENABLE_INDIC_STT=1 -- see _load_indic_stt_backends.
_indic_stt_backends: dict[str, STTBackend] = _load_indic_stt_backends()
# {} unless UDK_ENABLE_INDIC_KWS=1 -- see _load_indic_kws_backends.
_indic_kws_backends: dict[str, KWSBackend] = _load_indic_kws_backends()
# None unless UDK_ENABLE_SEPARATION=1 -- see _load_separator/separation.py.
_separator: SeparatorBackend | None = _load_separator()

app = FastAPI()


class StartRequest(BaseModel):
    user_id: str
    journey_id: str | None = None
    personal_udk_phrase: str | None = None
    # Which UDK phrase list/semantic matcher this journey uses (udks.py's
    # SUPPORTED_LANGUAGES) -- the language the 20 UDKs were shown to this
    # user in at login (Section 5), not auto-detected from their speech.
    language: str = "en"


class StopRequest(BaseModel):
    client_ts: float | None = None
    reason: str = "user_stopped"


@app.post("/v1/journeys/start", dependencies=[Depends(require_service_token)])
def start_journey(body: StartRequest):
    journey_id = body.journey_id or str(uuid.uuid4())

    if body.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, {"errors": [f"unsupported language {body.language!r}, must be one of {SUPPORTED_LANGUAGES}"]})

    personal_udk = SAMPLE_PERSONAL_UDK
    if body.personal_udk_phrase:
        result = enroll(body.user_id, body.personal_udk_phrase)
        if not result.ok:
            raise HTTPException(400, {"errors": result.errors})
        personal_udk = result.udk

    journey, created = _store.create_or_get(
        journey_id,
        body.user_id,
        _stt_backend,
        personal_udk,
        _audio_store,
        _kws_backend,
        _semantic_matcher,
        language=body.language,
        multilingual_semantic_matcher=_multilingual_semantic_matcher,
        stt_by_language=_indic_stt_backends,
        kws_by_language=_indic_kws_backends,
    )
    if created:
        # Covers the recovery case (rebuilt from durable storage after a
        # restart) as much as the brand-new one: any backlog audio may
        # contain a detection nobody's emitted an event for yet, since
        # the in-memory event history didn't survive a crash. No-op for
        # a genuinely fresh/empty journey.
        _run_incremental_detection(journey)
    return {
        "journey_id": journey.journey_id,
        "session_token": journey.session_token,
        "stream_endpoint": f"/v1/journeys/{journey.journey_id}/stream",
        "heartbeat_interval_s": HEARTBEAT_INTERVAL_S,
    }


@app.post("/v1/journeys/{journey_id}/stop")
def stop_journey(journey_id: str, _body: StopRequest):
    journey = _store.get(journey_id)
    if journey is None:
        raise HTTPException(404, "journey not found")
    if journey.status == "ACTIVE":
        _run_incremental_detection(journey, final=True)  # flush the tail segment
        journey.status = "COMPLETE"
        _db.save_journey(journey)
        _metrics.journey_completed()
    return {"journey_id": journey.journey_id, "status": "FINALIZING"}


@app.get("/metrics")
def get_metrics():
    """Section 11: 'a healthy-looking API can coexist with a completely
    broken detection pipeline' -- this is the pipeline's actual-work
    metrics, not request/response health. JSON, not Prometheus text
    format, since this is a single-process prototype snapshot, not a
    real scrape target."""
    return _metrics.snapshot()


@app.get("/v1/journeys/{journey_id}")
def get_journey(journey_id: str):
    journey = _store.get(journey_id)
    if journey is not None:
        return {
            "journey_id": journey.journey_id,
            "status": journey.status,
            "start_time": journey.started_at,
            "last_heartbeat_at": journey.last_heartbeat_at,
        }
    # Not live in this process, but may still be known durably (Section
    # 9: status should be queryable without needing the in-memory
    # journey rehydrated) -- a lightweight status-only read, not a full
    # AudioStore-backed recovery.
    row = _db.load_journey(journey_id)
    if row is not None:
        return {
            "journey_id": row["journey_id"],
            "status": row["status"],
            "start_time": row["started_at"],
            "last_heartbeat_at": row["last_heartbeat_at"],
        }
    raise HTTPException(404, "journey not found")


@app.get("/v1/journeys/{journey_id}/events")
def get_events(journey_id: str):
    journey = _store.get(journey_id)
    if journey is not None:
        return {"events": journey.events}
    if _db.load_journey(journey_id) is not None:
        return {"events": _db.load_events(journey_id)}
    raise HTTPException(404, "journey not found")


@app.get("/v1/journeys/{journey_id}/audio-url")
def get_audio_url(journey_id: str, user_id: str):
    """Section 10: audio access must be ownership-checked and go through
    a short-lived signed URL, never a permanent public path. Every
    request is audited (who, when, journey, outcome) -- not the audio
    itself, per Section 10's "never log content" rule."""
    owner = _journey_owner(journey_id)
    if owner is None:
        raise HTTPException(404, "journey not found")
    if owner != user_id:
        _audit_log.record(actor=user_id, action="request_audio_url", journey_id=journey_id, outcome="denied_not_owner")
        raise HTTPException(403, "not the journey owner")

    expires_at = time.time() + AUDIO_TOKEN_TTL_S
    token = _sign_audio_token(journey_id, expires_at)
    _audit_log.record(actor=user_id, action="request_audio_url", journey_id=journey_id, outcome="granted")
    return {"url": f"/v1/journeys/{journey_id}/audio?token={token}", "expires_at": expires_at}


@app.get("/v1/journeys/{journey_id}/audio")
def get_audio(journey_id: str, token: str):
    if not _verify_audio_token(journey_id, token):
        _audit_log.record(actor="unknown", action="read_audio", journey_id=journey_id, outcome="denied_invalid_token")
        raise HTTPException(403, "invalid or expired token")
    try:
        audio = _audio_store.read_full_audio(journey_id)
    except ValueError:
        _audit_log.record(actor="unknown", action="read_audio", journey_id=journey_id, outcome="denied_corrupt")
        raise HTTPException(500, "audio unavailable or corrupt")
    _audit_log.record(actor="unknown", action="read_audio", journey_id=journey_id, outcome="granted")
    return Response(content=audio, media_type="application/octet-stream")


@app.websocket("/v1/journeys/{journey_id}/stream")
async def stream_audio(websocket: WebSocket, journey_id: str, session_token: str):
    journey = _store.get(journey_id)
    if journey is None or journey.session_token != session_token or journey.status != "ACTIVE":
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                frame = message["bytes"]
                seq, _client_ts = FRAME_HEADER.unpack(frame[: FRAME_HEADER.size])
                pcm = frame[FRAME_HEADER.size :]
                new_events = _ingest_frame(journey, seq, pcm, _audio_store)
                journey.last_heartbeat_at = time.time()
                _db.save_journey(journey)
                await websocket.send_json(
                    {"type": "ack", "ack_seq": journey.next_expected_seq - 1, "server_ts": time.time()}
                )
                for event in new_events:
                    await websocket.send_json({"type": "event", **event})

            elif message.get("text") is not None:
                payload = json.loads(message["text"])
                if payload.get("type") == "heartbeat":
                    journey.last_heartbeat_at = time.time()
                    _db.save_journey(journey)
                    await websocket.send_json({"type": "heartbeat", "server_ts": time.time()})
    except WebSocketDisconnect:
        pass
