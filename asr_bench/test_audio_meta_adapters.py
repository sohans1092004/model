"""S2 tests: audio metadata + SHA-256 (audio_meta.py) and the dataset adapter contract
(adapters.py). All audio is generated at run time in a temp dir -- no binary fixtures, no real
dataset, no model. Same check() style as the repo's test_*.py.

    python asr_bench/test_audio_meta_adapters.py

The non-WAV (PyAV) checks run only where PyAV (`av`) is importable, and print [SKIP] otherwise.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import struct
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from asr_bench.adapters import (AdapterContractError, DatasetAdapter, ManifestRowError, SourceInfo,
                                SourceUtterance, check_namespaced)
from asr_bench.adapters import build_row as _build_row, build_rows as _build_rows
from asr_bench.audio_meta import (AudioFileMissing, AudioMetadataError, CorruptAudio, UnsupportedAudioFormat,
                                  read_audio_metadata, sha256_file)
from asr_bench.eligibility import select_eligible
from asr_bench.schema import FIELDS
from asr_bench.validate import validate_file

# Registry gate (source-registry stage): these S2/S3 tests run against a toy registry in which the
# toy sources are registered and authorised; the bundled registry authorises nothing.
from asr_bench.registry import SourceRegistry
TOY_REGISTRY = SourceRegistry.from_dict({"format": "asr_bench.source_registry/1", "registry_version": 1, "sources": {
    sid: {"name": sid, "family": "toy", "intended_use": "test", "acquisition_status": "toy", "licence": lic,
          "gate_status": "toy", "use_restriction": ur, "acquisition_authorised": True, "blockers": []}
    for sid, lic, ur in (("toy", "toy (test fixture)", "train_ok"), ("toyg", "toy gated licence (gate terms unread)", "blocked"),
                         ("toyev", "toy eval-only licence", "eval_only"))}})


def build_row(*a, **k):
    return _build_row(*a, registry=TOY_REGISTRY, **k)


def build_rows(*a, **k):
    return _build_rows(*a, registry=TOY_REGISTRY, **k)

passed = 0
failed = 0
skipped = 0


def check(name: str, condition: bool, detail="") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}" + (f"\n       {detail}" if detail != "" else ""))


def skip(name: str, why: str) -> None:
    global skipped
    skipped += 1
    print(f"[SKIP] {name} ({why})")


def raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception as e:  # wrong exception type
        print(f"       (raised {type(e).__name__}: {e})")
        return False
    return False


def write_wav(path: Path, rate: int, channels: int, frames: int, sampwidth: int = 2) -> bytes:
    """Stdlib PCM WAV; returns the raw sample bytes."""
    pcm = bytes((i * 7) % 251 for i in range(frames * channels * sampwidth))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(pcm)
    return pcm


def riff(tag: int, channels: int, rate: int, bits: int, data: bytes, *, extensible: bool = False,
         before_data: bytes = b"", declared_data: int | None = None) -> bytes:
    """Hand-built RIFF/WAVE bytes, for header variants the stdlib `wave` writer cannot make."""
    block = channels * bits // 8
    fmt = struct.pack("<HHIIHH", 0xFFFE if extensible else tag, channels, rate, rate * block, block, bits)
    if extensible:  # cbSize, valid bits, channel mask, SubFormat GUID (first 2 bytes = real tag)
        fmt += struct.pack("<HHI", 22, bits, 0) + struct.pack("<H", tag) + bytes(14)
    size = len(data) if declared_data is None else declared_data
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + before_data
    body += b"data" + struct.pack("<I", size) + data + (b"\x00" if len(data) & 1 else b"")
    return b"RIFF" + struct.pack("<I", len(body)) + body


tmp = Path(tempfile.mkdtemp(prefix="asr_bench_s2_"))
try:
    # --- A. metadata from real (generated) files --------------------------------------------------
    mono = tmp / "mono16k.wav"
    pcm = write_wav(mono, 16000, 1, 8000)
    m = read_audio_metadata(mono)
    check("16 kHz mono 8000 frames: rate/channels/frames/duration exact",
          (m.sample_rate_hz, m.channels, m.num_frames, m.duration_s) == (16000, 1, 8000, 0.5), m)
    check("WAV is read from the header (no decoding)", m.reader == "riff-header", m.reader)

    stereo = tmp / "stereo44k.wav"
    write_wav(stereo, 44100, 2, 44100)
    m2 = read_audio_metadata(stereo)
    check("44.1 kHz stereo: original rate and channels kept (no 16 kHz mono conversion)",
          (m2.sample_rate_hz, m2.channels, m2.duration_s) == (44100, 2, 1.0), m2)

    u8 = tmp / "u8_8k.wav"
    write_wav(u8, 8000, 1, 2000, sampwidth=1)
    check("8-bit 8 kHz: duration 0.25 s", read_audio_metadata(u8).duration_s == 0.25)

    f32 = tmp / "float32.wav"
    f32.write_bytes(riff(3, 1, 24000, 32, bytes(4 * 1200)))
    m3 = read_audio_metadata(f32)
    check("IEEE-float WAV: 1200 frames at 24 kHz = 0.05 s", (m3.sample_rate_hz, m3.num_frames, m3.duration_s) == (24000, 1200, 0.05), m3)

    ext = tmp / "extensible.wav"
    ext.write_bytes(riff(1, 2, 48000, 24, bytes(6 * 480), extensible=True))
    m4 = read_audio_metadata(ext)
    check("WAVE_FORMAT_EXTENSIBLE 24-bit stereo: 480 frames at 48 kHz", (m4.channels, m4.num_frames, m4.sample_rate_hz) == (2, 480, 48000), m4)

    odd = tmp / "odd_chunk.wav"
    odd.write_bytes(riff(1, 1, 16000, 16, bytes(2 * 160), before_data=b"LIST" + struct.pack("<I", 3) + b"abc\x00"))
    check("odd-sized chunk before data (word padding) is skipped correctly", read_audio_metadata(odd).num_frames == 160)

    empty_audio = tmp / "zero_frames.wav"
    write_wav(empty_audio, 16000, 1, 0)
    check("zero-frame WAV is reported as it is (0.0 s), not padded", read_audio_metadata(empty_audio).duration_s == 0.0)

    # --- B. SHA-256 = exact source-file bytes ----------------------------------------------------
    check("audio_sha256 equals hashlib.sha256 of the file's bytes", m.audio_sha256 == hashlib.sha256(mono.read_bytes()).hexdigest())
    check("audio_sha256 is reproducible (same file read twice)", read_audio_metadata(mono).audio_sha256 == m.audio_sha256)
    copy = tmp / "copy.wav"
    shutil.copyfile(mono, copy)
    check("byte-identical copy has the same audio_sha256", sha256_file(copy) == m.audio_sha256)
    flipped = bytearray(mono.read_bytes())
    flipped[-1] ^= 0x01
    changed = tmp / "one_byte_changed.wav"
    changed.write_bytes(bytes(flipped))
    check("one changed sample byte changes audio_sha256", sha256_file(changed) != m.audio_sha256)
    check("audio_sha256 is NOT the hash of the decoded PCM", m.audio_sha256 != hashlib.sha256(pcm).hexdigest())
    same_pcm = tmp / "same_pcm_other_header.wav"
    same_pcm.write_bytes(riff(1, 1, 16000, 16, pcm, before_data=b"LIST" + struct.pack("<I", 4) + b"note"))
    ms = read_audio_metadata(same_pcm)
    check("same samples, different header: same duration, DIFFERENT audio_sha256 (file-byte semantics)",
          ms.duration_s == m.duration_s and ms.audio_sha256 != m.audio_sha256)
    big = tmp / "big.wav"
    write_wav(big, 16000, 1, 1_600_000)  # 3.2 MB: more than one 1 MiB hashing block
    check("multi-block file hashes correctly", sha256_file(big) == hashlib.sha256(big.read_bytes()).hexdigest())

    # --- missing / unreadable --------------------------------------------------------------------
    check("missing file -> AudioFileMissing", raises(lambda: read_audio_metadata(tmp / "nope.wav"), AudioFileMissing))
    check("directory -> AudioMetadataError", raises(lambda: read_audio_metadata(tmp), AudioMetadataError))
    (tmp / "empty.wav").write_bytes(b"")
    check("empty file -> CorruptAudio", raises(lambda: read_audio_metadata(tmp / "empty.wav"), CorruptAudio))
    trunc = tmp / "truncated.wav"
    trunc.write_bytes(riff(1, 1, 16000, 16, bytes(100), declared_data=10_000))
    check("data chunk longer than the file -> CorruptAudio", raises(lambda: read_audio_metadata(trunc), CorruptAudio))
    partial = tmp / "partial_frame.wav"
    partial.write_bytes(riff(1, 2, 16000, 16, bytes(6)))
    check("data not a whole number of frames -> CorruptAudio", raises(lambda: read_audio_metadata(partial), CorruptAudio))
    nofmt = tmp / "no_fmt.wav"
    nofmt.write_bytes(b"RIFF" + struct.pack("<I", 12) + b"WAVE" + b"data" + struct.pack("<I", 0))
    check("WAVE without fmt chunk -> CorruptAudio", raises(lambda: read_audio_metadata(nofmt), CorruptAudio))
    rf64 = tmp / "rf64.wav"
    rf64.write_bytes(b"RF64" + bytes(40))
    check("RF64 -> UnsupportedAudioFormat (not guessed)", raises(lambda: read_audio_metadata(rf64), UnsupportedAudioFormat))
    junk = tmp / "junk.mp3"
    junk.write_bytes(b"not audio at all " * 20)
    check("non-audio bytes with PyAV disabled -> UnsupportedAudioFormat",
          raises(lambda: read_audio_metadata(junk, allow_pyav=False), UnsupportedAudioFormat))
    check("non-audio bytes -> AudioMetadataError either way (with or without PyAV)",
          raises(lambda: read_audio_metadata(junk), AudioMetadataError))
    adpcm = tmp / "adpcm.wav"
    adpcm.write_bytes(riff(2, 1, 8000, 4, bytes(256)))
    check("compressed codec inside WAV is not counted from the header (needs a decoder)",
          raises(lambda: read_audio_metadata(adpcm, allow_pyav=False), UnsupportedAudioFormat))

    # --- non-WAV via PyAV (optional) --------------------------------------------------------------
    try:
        import av
    except ImportError:
        av = None
    if av is None:
        for name in ("FLAC mono 22.05 kHz via PyAV", "FLAC stereo 48 kHz via PyAV", "FLAC with PyAV disabled"):
            skip(name, "PyAV not installed here")
    else:
        def make_flac(path: Path, rate: int, n: int, layout: str) -> None:
            ch = 2 if layout == "stereo" else 1
            with av.open(str(path), "w", format="flac") as out:
                st = out.add_stream("flac", rate=rate, layout=layout)
                fr = av.AudioFrame(format="s16", layout=layout, samples=n)
                fr.planes[0].update(struct.pack(f"<{n * ch}h", *(900 if i % 2 else -900 for i in range(n * ch))))
                fr.sample_rate, fr.pts = rate, 0
                for pkt in [*st.encode(fr), *st.encode(None)]:
                    out.mux(pkt)
        fl = tmp / "mono.flac"
        make_flac(fl, 22050, 2205, "mono")
        mf = read_audio_metadata(fl)
        check("FLAC mono 22.05 kHz via PyAV: 2205 frames = 0.1 s",
              (mf.sample_rate_hz, mf.channels, mf.num_frames, mf.duration_s, mf.reader) == (22050, 1, 2205, 0.1, "pyav-decoded"), mf)
        fl2 = tmp / "stereo.flac"
        make_flac(fl2, 48000, 480, "stereo")
        mf2 = read_audio_metadata(fl2)
        check("FLAC stereo 48 kHz via PyAV", (mf2.channels, mf2.sample_rate_hz, mf2.num_frames) == (2, 48000, 480), mf2)
        check("FLAC with PyAV disabled -> UnsupportedAudioFormat",
              raises(lambda: read_audio_metadata(fl, allow_pyav=False), UnsupportedAudioFormat))
        check("FLAC audio_sha256 is still the file bytes", mf.audio_sha256 == hashlib.sha256(fl.read_bytes()).hexdigest())

    # --- C/D. adapter contract ---------------------------------------------------------------------
    SRC = SourceInfo("toy", "0", "toy (test fixture)", "train_ok")

    def utt(**changes) -> SourceUtterance:
        base = dict(
            source_utt_id="0001", audio_path="mono16k.wav", speaker_id="toy:spk01", session_id="toy:sess01",
            recording_id=None, transcript_ref="help me", transcript_romanised=None, tokens=None,
            language_primary="en-IN", languages_present=["en-IN"], is_code_switched=False, cmi=None,
            script="Latn", english_word_script=None, provenance="acted_scripted", environment="quiet",
            condition_device="phone_hand", condition_real_or_synthetic="real", aug_recipe=None, seed=None,
            snr_db=None, clipping_ratio=None, overlap=False, overlap_spans=None, overlap_rel_db=None,
            safety_tags=None, keyword_spans=None, licence=None, use_restriction=None)
        base.update(changes)
        return SourceUtterance(**base)

    check("SourceUtterance has no defaults: omitting a field is a TypeError",
          raises(lambda: SourceUtterance(source_utt_id="x", audio_path="a.wav"), TypeError))
    check("DatasetAdapter cannot be instantiated without source/utterances",
          raises(lambda: DatasetAdapter(), TypeError))

    row = build_row(SRC, utt(), split="dev", audio_root=tmp)
    check("build_row returns every §3 field, in schema order", list(row) == list(FIELDS), list(row))
    check("utt_id = '<source_dataset>:<source_utt_id>'", row["utt_id"] == "toy:0001")
    check("audio metadata is MEASURED from the file", (row["sample_rate_hz"], row["duration_s"], row["channels"],
          row["audio_sha256"]) == (16000, 0.5, 1, m.audio_sha256), row)
    check("audio_path is written as the adapter gave it", row["audio_path"] == "mono16k.wav")
    check("source licence/use_restriction are carried onto the row",
          (row["licence"], row["use_restriction"]) == ("toy (test fixture)", "train_ok"))
    check("split comes from the caller", row["split"] == "dev")
    check("absolute audio_path needs no audio_root", build_row(SRC, utt(audio_path=str(mono)), split="dev")["audio_sha256"] == m.audio_sha256)
    check("relative audio_path without audio_root -> AdapterContractError",
          raises(lambda: build_row(SRC, utt(), split="dev"), AdapterContractError))
    check("missing audio -> AudioFileMissing (not a row with invented metadata)",
          raises(lambda: build_row(SRC, utt(audio_path="gone.wav"), split="dev", audio_root=tmp), AudioFileMissing))
    check("zero-frame audio -> ManifestRowError (duration_s must be > 0)",
          raises(lambda: build_row(SRC, utt(audio_path="zero_frames.wav"), split="dev", audio_root=tmp), ManifestRowError))
    check("an invalid enum from the adapter -> ManifestRowError",
          raises(lambda: build_row(SRC, utt(environment="market"), split="dev", audio_root=tmp), ManifestRowError))
    try:
        build_row(SRC, utt(environment="market"), split="dev", audio_root=tmp)
    except ManifestRowError as e:
        check("ManifestRowError carries the schema issues", any(i.field == "environment" for i in e.issues), e.issues)
    check("empty source_utt_id -> AdapterContractError",
          raises(lambda: build_row(SRC, utt(source_utt_id=" "), split="dev", audio_root=tmp), AdapterContractError))
    for bad in (SourceInfo("", "0", "x", "train_ok"), SourceInfo("toy", "0", "", "train_ok"),
                SourceInfo("toy", "0", "x", "research"), SourceInfo("to:y", "0", "x", "train_ok")):
        check(f"bad SourceInfo {bad} -> AdapterContractError",
              raises(lambda: build_row(bad, utt(), split="dev", audio_root=tmp), AdapterContractError))

    # --- speaker / session / recording namespacing contract ----------------------------------------
    for field, val in (("speaker_id", "spk01"), ("speaker_id", "other:spk01"), ("speaker_id", "toy:"),
                       ("session_id", "sess01"), ("recording_id", "rec1")):
        check(f"{field}={val!r} is not namespaced for source 'toy' -> AdapterContractError",
              raises(lambda: build_row(SRC, utt(**{field: val}), split="dev", audio_root=tmp), AdapterContractError))
    check("namespaced 'toy:spk01' / 'toy:sess01' / 'toy:rec1' are accepted",
          build_row(SRC, utt(recording_id="toy:rec1"), split="dev", audio_root=tmp)["recording_id"] == "toy:rec1")
    check("the namespace check does not rewrite IDs (no universal transformation)",
          raises(lambda: check_namespaced("toy", "speaker_id", "SPK-01"), AdapterContractError))
    check("a source-local ID containing ':' is fine once prefixed", not raises(
        lambda: check_namespaced("toy", "speaker_id", "toy:a:b"), AdapterContractError))
    check("null speaker_id is allowed by the adapter contract ...",
          build_row(SRC, utt(speaker_id=None), split="eval_only", audio_root=tmp)["speaker_id"] is None)
    check("... but the schema still rejects it in a speaker-disjoint split",
          raises(lambda: build_row(SRC, utt(speaker_id=None), split="dev", audio_root=tmp), ManifestRowError))

    # --- licence / blocked sources ------------------------------------------------------------------
    BLK = SourceInfo("toyg", "0", "toy gated licence (gate terms unread)", "blocked")
    blk_utt = utt(speaker_id="toyg:spk1", session_id=None)
    brow = build_row(BLK, blk_utt, split="eval_only", audio_root=tmp)
    check("blocked source builds an inventory row (split eval_only)", brow["use_restriction"] == "blocked")
    check("blocked source row in dev -> ManifestRowError",
          raises(lambda: build_row(BLK, blk_utt, split="dev", audio_root=tmp), ManifestRowError))
    check("an utterance cannot lift a blocked source's restriction",
          raises(lambda: build_row(BLK, dataclasses.replace(blk_utt, use_restriction="train_ok"), split="eval_only",
                                   audio_root=tmp), AdapterContractError))
    clip = build_row(SRC, utt(licence="toy CC0 clip", use_restriction="eval_only"), split="test", audio_root=tmp)
    check("per-utterance licence override is recorded on the row",
          (clip["licence"], clip["use_restriction"]) == ("toy CC0 clip", "eval_only"))
    check("blocked inventory row from an adapter is never eligible",
          select_eligible([brow], "eval_only")[0] == [])

    # P-S2-3 (resolved): monotone precedence train_ok < eval_only < blocked; source = ceiling
    EVO = SourceInfo("toyev", "0", "toy eval-only licence", "eval_only")
    ev_utt = utt(speaker_id="toyev:spk1", session_id=None)
    check("P-S2-3: eval_only source + train_ok utterance (relaxing) -> AdapterContractError",
          raises(lambda: build_row(EVO, dataclasses.replace(ev_utt, use_restriction="train_ok"), split="test",
                                   audio_root=tmp), AdapterContractError))
    check("P-S2-3: eval_only source + eval_only utterance (equal) is accepted",
          build_row(EVO, dataclasses.replace(ev_utt, use_restriction="eval_only"), split="test", audio_root=tmp)["use_restriction"] == "eval_only")
    check("P-S2-3: eval_only source + blocked utterance (stricter) is accepted as inventory",
          build_row(EVO, dataclasses.replace(ev_utt, use_restriction="blocked"), split="eval_only", audio_root=tmp)["use_restriction"] == "blocked")
    check("P-S2-3: train_ok source + blocked utterance -> blocked row",
          build_row(SRC, utt(use_restriction="blocked"), split="eval_only", audio_root=tmp)["use_restriction"] == "blocked")
    check("P-S2-3: blocked source + blocked utterance stays blocked",
          build_row(BLK, dataclasses.replace(blk_utt, use_restriction="blocked"), split="eval_only", audio_root=tmp)["use_restriction"] == "blocked")
    check("P-S2-3: blocked source + eval_only utterance (relaxing) -> AdapterContractError",
          raises(lambda: build_row(BLK, dataclasses.replace(blk_utt, use_restriction="eval_only"), split="eval_only",
                                   audio_root=tmp), AdapterContractError))
    check("P-S2-3: unknown utterance use_restriction -> AdapterContractError",
          raises(lambda: build_row(SRC, utt(use_restriction="research"), split="dev", audio_root=tmp), AdapterContractError))

    # --- adapter end to end + manifest compatibility --------------------------------------------------
    class ToyAdapter(DatasetAdapter):
        source = SRC

        def utterances(self):
            yield utt(source_utt_id="a", audio_path="mono16k.wav")
            yield utt(source_utt_id="b", audio_path="stereo44k.wav", speaker_id="toy:spk02", session_id="toy:sess02")
            yield utt(source_utt_id="c", audio_path="missing.wav", speaker_id="toy:spk03", session_id="toy:sess03")
            yield utt(source_utt_id="d", audio_path="float32.wav", speaker_id="bare03", session_id="toy:sess04")

    rows, failures = build_rows(ToyAdapter(), lambda u: "test" if u.source_utt_id == "b" else "dev", audio_root=tmp)
    check("build_rows: good utterances become rows", [r["utt_id"] for r in rows] == ["toy:a", "toy:b"], rows)
    check("build_rows: failures are collected with their cause, not fatal",
          [(i, type(e).__name__) for i, e in failures] == [("c", "AudioFileMissing"), ("d", "AdapterContractError")], failures)
    manifest = tmp / "manifest.jsonl"
    manifest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    read, issues = validate_file(manifest)
    check("manifest compatibility: adapter rows written to JSONL pass the S1 validator",
          len(read) == 2 and not [i for i in issues if i.level == "error"], [str(i) for i in issues])
    check("manifest compatibility: eligibility sees them per split",
          len(select_eligible(rows, "dev")[0]) == 1 and len(select_eligible(rows, "test")[0]) == 1)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (f", {skipped} SKIPPED" if skipped else "")
      + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
