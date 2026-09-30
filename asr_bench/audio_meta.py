"""Audio metadata for the Phase 2A manifest (§3): sample_rate_hz, duration_s, channels, audio_sha256.

    audio_sha256 = SHA-256 of the exact source audio file bytes.

Not of decoded PCM, not of a resampled copy: two files with identical samples but different
headers hash differently, and that is intended. Near-duplicate / audio-content fingerprinting
(Phase 1 §19) is a separate, later concern and is not done here.

Metadata describes the ORIGINAL file (§3: "Original rate kept; 16 kHz copy derived"). The
repository's usual loaders (librosa.load, faster_whisper.decode_audio) resample to 16 kHz mono,
so they cannot report the original rate or channel count and are not used.

Readers, chosen by file CONTENT, not extension:
  - RIFF/WAVE: parsed from the header with the stdlib (no decoding, exact). PCM, IEEE float,
    A-law, mu-law and WAVE_FORMAT_EXTENSIBLE of PCM/float. duration = data bytes / block
    align / rate.
  - anything else: PyAV (`av`), only if it is importable. It is already installed wherever
    faster-whisper is (faster-whisper decodes through it); asr_bench does not add it as a
    requirement (PENDING_DECISIONS.md, Q11 / P-S2-4). duration = decoded samples / rate
    (P-S2-1). Without PyAV such files raise UnsupportedAudioFormat.
"""
from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass
from pathlib import Path

_CHUNK = 1 << 20

# WAVE format tags whose block_align is exactly one sample frame, so frames = bytes / block_align.
_FRAME_FORMATS = {0x0001: "pcm", 0x0003: "ieee_float", 0x0006: "alaw", 0x0007: "mulaw"}
_EXTENSIBLE = 0xFFFE


class AudioMetadataError(Exception):
    """The file's metadata could not be established; nothing is guessed."""


class AudioFileMissing(AudioMetadataError):
    pass


class UnsupportedAudioFormat(AudioMetadataError):
    pass


class CorruptAudio(AudioMetadataError):
    pass


@dataclass(frozen=True)
class AudioMetadata:
    sample_rate_hz: int
    duration_s: float
    channels: int
    audio_sha256: str
    num_frames: int  # samples per channel
    reader: str  # how the numbers were obtained: "riff-header" or "pyav-decoded"


def sha256_file(path: str | os.PathLike) -> str:
    """SHA-256 of the exact bytes of `path` (streamed, any size)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def read_audio_metadata(path: str | os.PathLike, allow_pyav: bool = True) -> AudioMetadata:
    p = Path(path)
    if not p.exists():
        raise AudioFileMissing(f"{p}: no such file")
    if not p.is_file():
        raise AudioMetadataError(f"{p}: not a regular file")
    try:
        size = p.stat().st_size
        with open(p, "rb") as f:
            head = f.read(12)
    except OSError as e:
        raise AudioMetadataError(f"{p}: unreadable ({e})") from e
    if size == 0:
        raise CorruptAudio(f"{p}: empty file")
    if head[:4] == b"RF64":
        raise UnsupportedAudioFormat(f"{p}: RF64 (64-bit WAV) is not supported")
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        wav = _read_wav(p, size)
        if wav is not None:
            frames, rate, channels = wav
            return AudioMetadata(rate, frames / rate, channels, sha256_file(p), frames, "riff-header")
        # a WAVE container holding a compressed codec (ADPCM, MP3-in-WAV...): only a decoder can count it
    if not allow_pyav:
        raise UnsupportedAudioFormat(f"{p}: not a PCM/float/A-law/mu-law WAV and PyAV is disabled")
    frames, rate, channels = _read_pyav(p)
    return AudioMetadata(rate, frames / rate, channels, sha256_file(p), frames, "pyav-decoded")


def _read_wav(p: Path, size: int) -> tuple[int, int, int] | None:
    """(frames, rate, channels) from the RIFF header, or None for a codec that needs decoding."""
    fmt = None
    data_size = None
    with open(p, "rb") as f:
        f.seek(12)
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            cid, csize = hdr[:4], struct.unpack("<I", hdr[4:])[0]
            start = f.tell()
            if cid == b"fmt ":
                body = f.read(csize)
                if len(body) < 16:
                    raise CorruptAudio(f"{p}: fmt chunk is {len(body)} bytes, needs at least 16")
                tag, channels, rate, _byte_rate, block_align, bits = struct.unpack("<HHIIHH", body[:16])
                if tag == _EXTENSIBLE:
                    if len(body) < 40:
                        raise CorruptAudio(f"{p}: WAVE_FORMAT_EXTENSIBLE fmt chunk is too short")
                    tag = struct.unpack("<H", body[24:26])[0]  # first two bytes of the SubFormat GUID
                fmt = (tag, channels, rate, block_align, bits)
            elif cid == b"data":
                if start + csize > size:
                    raise CorruptAudio(f"{p}: data chunk declares {csize} bytes but only {size - start} follow (truncated?)")
                data_size = csize
            f.seek(start + csize + (csize & 1))  # chunks are word-aligned
            if data_size is not None and fmt is not None:
                break
    if fmt is None:
        raise CorruptAudio(f"{p}: WAVE file has no fmt chunk")
    if data_size is None:
        raise CorruptAudio(f"{p}: WAVE file has no data chunk")
    tag, channels, rate, block_align, _bits = fmt
    if tag not in _FRAME_FORMATS:
        return None
    if channels < 1 or rate < 1 or block_align < 1:
        raise CorruptAudio(f"{p}: invalid fmt (channels={channels}, rate={rate}, block_align={block_align})")
    if data_size % block_align:
        raise CorruptAudio(f"{p}: data size {data_size} is not a whole number of {block_align}-byte frames")
    return data_size // block_align, rate, channels


def _read_pyav(p: Path) -> tuple[int, int, int]:
    try:
        import av
    except ImportError as e:
        raise UnsupportedAudioFormat(f"{p}: not a PCM WAV, and PyAV (`av`) is not installed to read it") from e
    try:
        with av.open(str(p)) as container:
            streams = container.streams.audio
            if len(streams) != 1:
                raise UnsupportedAudioFormat(f"{p}: {len(streams)} audio streams; exactly one is required (P-S2-6)")
            frames, rate, channels = 0, None, None
            for frame in container.decode(streams[0]):
                fr, ch = frame.sample_rate, len(frame.layout.channels)
                if rate is None:
                    rate, channels = fr, ch
                elif (fr, ch) != (rate, channels):
                    raise UnsupportedAudioFormat(f"{p}: sample rate/channels change mid-stream ({rate}/{channels} -> {fr}/{ch})")
                frames += frame.samples
    except AudioMetadataError:
        raise
    except Exception as e:  # PyAV raises its own error types for unreadable/corrupt input
        raise CorruptAudio(f"{p}: PyAV could not decode it ({type(e).__name__}: {e})") from e
    if rate is None or frames == 0:
        raise CorruptAudio(f"{p}: no decodable audio")
    return frames, rate, channels
