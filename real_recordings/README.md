Drop real `.wav` recordings here, then run `python3 evaluate_real_recordings.py`
from the project root. See that script's module docstring for the full
naming convention and format requirements. Quick version:

- `positives/UDK_01.wav`, `positives/UDK_01_alice.wav`, `positives/UDK_08_take2.wav`
  — filename must start with the UDK id (see `udks.py`) it's a recording of.
- `negatives/anything.wav` — ordinary speech that should never trigger.
- 16-bit PCM WAV, any sample rate/channels (auto-resampled). Convert other
  formats first: `ffmpeg -i recording.m4a -ar 16000 -ac 1 -sample_fmt s16 UDK_01.wav`

Both folders are empty until you add real recordings — nothing here is
synthetic or fabricated.
