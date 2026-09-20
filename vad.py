"""
Voice Activity Detection wrapper around webrtcvad.

Per Section 2 of the review: VAD should bias toward treating ambiguous
audio as speech, not silence, so a low aggressiveness setting is the
default. Frames are 16-bit mono PCM at 8/16/32/48kHz, 10/20/30ms each,
which is what webrtcvad requires.
"""

from __future__ import annotations

import webrtcvad
from dataclasses import dataclass

SAMPLE_RATE = 16_000
FRAME_MS = 30
FRAME_BYTES = int(SAMPLE_RATE * (FRAME_MS / 1000.0)) * 2  # 16-bit samples


@dataclass
class SpeechSegment:
    start_ms: int
    end_ms: int
    pcm: bytes


class VAD:
    def __init__(self, aggressiveness: int = 1, pre_roll_ms: int = 1500, post_roll_ms: int = 1500):
        """
        aggressiveness: 0 (most permissive / most likely to call things
        speech) to 3 (most aggressive at rejecting non-speech). Section 2
        recommends biasing toward speech, so this defaults low.
        """
        self._vad = webrtcvad.Vad(aggressiveness)
        self.pre_roll_frames = max(1, pre_roll_ms // FRAME_MS)
        self.post_roll_frames = max(1, post_roll_ms // FRAME_MS)

    def _frames(self, pcm: bytes):
        for i in range(0, len(pcm) - FRAME_BYTES + 1, FRAME_BYTES):
            yield pcm[i : i + FRAME_BYTES]

    def total_ms(self, pcm: bytes) -> int:
        """Duration accounted for by whole frames in this buffer, in the
        same units as SpeechSegment.end_ms. Callers use this to tell
        whether a segment has "cleared" the buffer's tail -- i.e. more
        audio has arrived since it ended, proving it's done growing --
        without needing to know FRAME_MS/FRAME_BYTES themselves."""
        return (len(pcm) // FRAME_BYTES) * FRAME_MS

    def segment_speech(self, pcm: bytes) -> list[SpeechSegment]:
        """
        Split raw 16kHz mono PCM into speech segments, each padded with
        pre-roll/post-roll (Section 2: don't cut exactly at the VAD
        boundary, or a detection loses the context around it).
        """
        frames = list(self._frames(pcm))
        flags = [self._vad.is_speech(f, SAMPLE_RATE) for f in frames]

        segments: list[SpeechSegment] = []
        i = 0
        n = len(flags)
        while i < n:
            if flags[i]:
                start = max(0, i - self.pre_roll_frames)
                j = i
                while j < n and flags[j]:
                    j += 1
                end = min(n, j + self.post_roll_frames)
                seg_pcm = b"".join(frames[start:end])
                segments.append(
                    SpeechSegment(
                        start_ms=start * FRAME_MS,
                        end_ms=end * FRAME_MS,
                        pcm=seg_pcm,
                    )
                )
                i = end
            else:
                i += 1
        return segments
