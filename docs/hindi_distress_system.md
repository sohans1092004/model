# Hindi + English distress detection — system card (2026-10-05)

**Status: pilot-ready design with measured results, not production-ready.** See *Go-live checklist*.

In this repo: `safety_router/` wired into `api.py` behind `UDK_ENABLE_HINDI` (off by default; see
`safety_router/README.md`). Evaluation scripts named below (`route_eval.py`, `train_frames.py`, …) and `Model/`
(the live English checkout they were measured against) belong to the research line of work, not to this branch.

What it detects:
- one of the **20 distress phrases said live**, in **Hindi** (Hindi system) or **English** (the live English system);
- **sustained screaming / crying** in any language (the live scream trigger).

What it does not detect (known gap): danger expressed **in other words** without those phrases, e.g. an attacker's
threat or "छोड़ो उसे!". Five approaches were tried and none worked without real recordings of the situation
(see *Limitations*).

## 1. Combined system: audio of unknown language

```
speech segment (VAD, <= 8 s)
  ├─ language ID (Whisper small, one encoder pass): P(language) for each supported language, renormalised
  ├─ route: take the most likely languages until their probability sums to >= 0.95 (cap 3)
  │      usually 1 language  -> only that language's system
  │      mixed / short / noisy -> the top 2 -> both, the higher decision wins (ALERT > VERIFY > none)
  ├─ scream trigger runs on EVERY segment, whatever the route (sound is language-independent)
  └─ final: ALERT (alert contacts) / VERIFY (ask the user "are you safe?") / none
```

Why per segment: the app currently fixes the language per session and needs ~18 s of agreeing audio to switch, so
a cry in the "other" language (a Hindi conversation, then "help me!") would go to the wrong system.
Why route at all instead of always running every system: the English system run on Hindi speech misreads it
(Whisper-English "hears" English words in Hindi audio), and false asks would add up across languages.
Adding a language later = its own system + one measurement of its false alarms on the other languages' speech;
the routing rule does not change.

## 2. The two language systems

| | English (live system, `Model/`, unchanged) | Hindi (this repo) |
|---|---|---|
| speech recognition | Whisper small.en + Parakeet TDT 0.6B v2 (stronger decision wins) | IndicConformer 600M RNNT |
| phrase match | exact / fuzzy / MiniLM semantic on the 20 English phrases | LaBSE similarity to the 20 Hindi phrases ([A]) |
| context check | STT confidence gate, BEATs corroboration, intent veto (mDeBERTa) | MuRIL frame classifier ([B]): live vs story / report / negation / joke, 30 s context |
| decision | `udk_engine` + `api._run_incremental_detection` | `safety_router.hindi.decide`: skip if ≥ 15 % English function words; [A] > 0.55 → ALERT if [B] ≥ 0.7, VERIFY if [B] ≥ 0.02; [A] > 0.45 and [B] ≥ 0.8 → ALERT (bystander) |

Hindi [B] weights: private HF repo `sohans1092004/hindi-distress-frame`, tag `v2-2026-10-05` = commit
`be81da55f40d6ea3fc1dca859ac85ed218eca32d` (pinned in `safety_router.hindi`, SHA-256
`4359c62b7bc1cb29cf2f42262a6b83f2260bcc8afc599d91efb1371ab0d27478`, checked on load; local copy
`frame_model_updated.pt`; rollback tag `v1-2026-10-03`), retrained 2026-10-05 with
`train_frames.py --exclude-style TGT --folds 0 --real-neg labels_v2.jsonl --extra-neg drama_negatives.jsonl tvphone_negatives.jsonl`
(adds 1,688 pilot drama windows and 3,000 TV-serial / phone-talk / crime-show windows as benign, Claude-labelled,
live-danger windows and their neighbours left out). Previous weights `frame_model.pt` (2026-10-03, SHA-256 `1d0ff14c…`)
used the old rule (always VERIFY when [A] > 0.55; bystander [B] ≥ 0.9); the sections below that predate 2026-10-05 measured it.

## 3. Measured results

### TV / phone-talk false alarms: retrained [B] + ask threshold (2026-10-05)
Hindi system, previous ([B] 2026-10-03, old rule) → current ([B] retrained, rule above). **Sealed** = 11 new videos
collected with the training ones but held out by video and read only for this measurement.

| audio | hours | previous ALERT/h | previous asks/h | **current ALERT/h** | **current asks/h** |
|---|---|---|---|---|---|
| sealed phone talk | 1.2 | 0.0 | 29.7 | **0.8** | **0.8** |
| sealed TV serial | 0.8 | 1.3 | 32.4 | **0.0** | **1.3** |
| sealed crime show | 0.5 | 1.9 | 20.6 | **0.0** | **0.0** |
| fresh phone talk | 1.5 | 6.6 | 28.2 | **0.0** | **0.7** |
| fresh TV serial | 2.4 | 0.4 | 26.0 | **0.0** | **0.4** |
| fresh crime shows | 7.8 | 2.9 | 18.4 | **0.6** | **2.2** |
| pilot drama, dev episodes | 2.5 | 1.2 | 17.5 | **0.0** | **0.0** |
| fresh street vlogs | 2.2 | 0.0 | 3.6 | 0.0 | 0.0 |

Danger side, same change: Hindi cries 47/2/1 → **48/0/2** (alert/ask/missed); lost: "दूर हटो… मैं पुलिस को कॉल कर रही
हूं" ([B] 0.08 → 0.004, it resembles playful "दूर रहो" in couple calls); English cries 18/22/10 → 18/18/14 (the 4 were
Hindi-system asks on misheard English); Threat Detection clips ([B] ≥ 0.7 alone) 106 → 104 of 108; 400 benign test
sentences flagged 23 → 30. Caveats: the fresh set and the cries were looked at while choosing the ask threshold (0.02)
and the bystander cut (0.8), so only the sealed rows are untouched; the sealed set is small (2.5 h).

### Combined system, small mixed audio test (`route_eval.py`, 2026-10-05)
English side = the deployed English path with byte-identical copies of `Model/` files (intent gate on).

| | English system alone (today's app) | Hindi system alone | **Combined** |
|---|---|---|---|
| false ALERTs, all benign audio | 0 | 0 | **0** |
| asks/h, English / Hinglish speech (0.5 h) | 4.0 | 0.0 | **4.0** |
| asks/h, Hindi speech (0.9 h) | 2.2 | 2.2 | **2.2** |
| 23 recorded ordinary clips: clips with an ask | 1 | 2 | **2** |
| Hindi cries for help (50): alert / ask / missed | 0 / 8 / 42 | 47 / 2 / 1 | **47 / 2 / 1** |
| English cries for help (50): alert / ask / missed | 18 / 17 / 15 | 0 / 18 / 32 | **18 / 22 / 10** |
| 7 recorded danger clips (mostly Tamil/Telugu/Hinglish) | 0 / 3 / 4 | 0 / 5 / 2 | **0 / 5 / 2** |

### Hindi system alone, larger tests
| test | result |
|---|---|
| unseen benign speech (27 held-out videos: podcasts, debates, crime news; 5.9 h) | 0.0 ALERT/h, 1.7 VERIFY/h |
| real Hindi danger clips (Threat Detection Audio, 108) | 102 ALERT, 4 VERIFY, 2 missed |
| fresh untouched genres (18 h): street vlogs | 0.0 ALERT/h, 3.6 VERIFY/h |
| fresh: TV serials / crime shows (previous [B] and rule; now 0.0 / 0.6 ALERT/h, 0.4 / 2.2 asks/h, see above) | 0.4 / 3.6 ALERT/h, 26 / 18.5 VERIFY/h |

### Scream trigger (live rule) on Hindi audio (60 h)
Fires on 54 % of real screams, 1 % of non-screams; 0–0.3 asks/h on podcasts/news/debates, 1–2.8 on serials,
crime shows and phone talks, 4.7 on street vlogs (mostly "Children shouting").

### Latency per speech segment (`latency_eval.py`, Kaggle T4, 2026-10-05, 57 real segments per side)

| route (time from end of segment to decision) | **GPU, onnxruntime-gpu 1.22.0** median / p95 | CPU fallback (CUDA mismatch) median / p95 |
|---|---|---|
| Hindi only | **0.43 s / 0.51 s** | 1.8 s / 2.3 s |
| English only | **1.04 s / 3.26 s** | 2.0 s / 4.2 s |
| both, in parallel (unsure segments) | **1.04 s / 3.26 s** | 2.1 s / 4.2 s |
| both, one after the other | 1.39 s / 3.68 s | 3.8 s / 6.6 s |

Per stage on GPU (median / p95, ms): language ID 59 / 75 · Whisper small.en 326 / 2612 · Parakeet 112 / 143
(CPU: 1146) · scream trigger 329 / 378 · scream score 38 / 45 · English engine 58 / 122 · intent gate 0 / 26 ·
IndicConformer 351 / 423 (CPU: 1704) · LaBSE 10 / 10 · MuRIL [B] 13 / 14.

Reading: the Hindi route decides in about half a second. The English route's median is ~1 s and its slow tail
(3.3 s p95) is almost entirely Whisper's temperature retries on hard audio; its stages also run one after another
(Whisper, Parakeet, scream trigger) and could run concurrently. Processing starts when VAD closes the segment
(≤ 8 s of speech + post-roll), so a short shout is decided ~1–2 s after it ends. Run the two language systems in
parallel for unsure segments. The onnxruntime build must match the server's CUDA: the latest needs CUDA 13; with
CUDA 12 use 1.22.x, otherwise both ONNX models silently fall back to CPU (4–5× slower).

How much to trust these: the combined test is small (< 2 h, 107 danger clips). Real-speech danger labels are
Claude's under the owner's rule (danger = the speaker or listener is in danger right now), not a native speaker's.
Parts of the Hindi tuning used its own test sets, so the Hindi numbers are somewhat optimistic; the English system
has a sealed-test protocol, the Hindi side has not been sealed-tested.

## 4. Limitations

1. **Danger without the phrases is not detected.** Tried: LLM-written scenes, TTS→ASR training text, translated
   911 calls, 32 real labelled drama windows, acoustic (screams), an open LLM as judge, and a second phrase list
   of threats (it reached 25/31 danger windows but raised asks to 96/h, i.e. one every ~40 s). What would work:
   300–500 phone recordings of real situations (victim, companion, attacker) plus look-alikes.
2. **Asks on dialogue-heavy TV / phone talk**: fixed 2026-10-05 (was 18–32 asks/h and up to 6.6 ALERT/h; now ≤ 2.2
   asks/h and ≤ 0.8 ALERT/h, section 3). The cost is that a real cry phrased like everyday couple banter ("दूर हटो…")
   can now be scored benign; fixing that needs real recordings of heated danger.
3. **Hinglish forms of the phrases** ("help karo", "मुझे help चाहिए") are not targeted by either system.
4. Languages other than English and Hindi: covered only by the scream trigger (and the English system's other
   language backends, not evaluated here).
5. English-system open issues listed in `Model/CONTEXT.md` (e.g. silent MockSTT on Whisper load failure).

## 5. Go-live checklist

| # | item | status |
|---|---|---|
| 1 | Hindi system integrated into the app's streaming path (`api.py`) as the router above | done on branch `hindi-distress`: behind `UDK_ENABLE_HINDI` (off), fallbacks to the English path, `test_hindi_routing.py`; not merged or deployed |
| 2 | [B] weights versioned and pinned | done 2026-10-05: private HF repo, tags v1/v2, commit pinned, SHA-256 checked on load |
| 3 | GPU builds of onnxruntime matching the server's CUDA, pinned (latest needs CUDA 13; for CUDA 12 use 1.22.x) — verified on Kaggle: 1.22.0 puts Parakeet and IndicConformer on GPU (4–10× faster) | fix known; server not done |
| 4 | end-to-end latency on the production server | Kaggle T4 GPU: Hindi 0.43 s, English 1.04 s median (3.3 s p95) per segment; server not measured |
| 5 | sealed Hindi + mixed test, ideally checked by a native Hindi speaker | not done |
| 6 | ask rate on TV / phone-talk audio | done 2026-10-05: retrained [B] + ask threshold, ≤ 2.2 asks/h (section 3) |
| 7 | user-facing wording for VERIFY ("are you safe?") vs ALERT agreed | open |

## 6. Reproduce

Kaggle (GPU T4) unless noted; full commands and history in `HANDOFF_HINDI_SAFETY.md`.
- TV/phone fix: `collect.py --sources sources_tvphone.json --exclude …` (Kaggle) → `public/tvphone_negatives.jsonl`
  (Claude labels) → `train_frames.py … --extra-neg …` (Kaggle) → local comparison on fresh, pilot dev, sealed, cries
- Hindi: `train_frames.py` (train [B]), `heldout_eval.py --test-split-only`, `e2e_eval.py`, `score_fresh.py`
- Scream trigger on Hindi audio: `acoustic_eval.py`
- Combined system: `route_eval.py build | en | hi | report` (English side uses copies of `Model/` files; `Model/`
  itself is never modified)
