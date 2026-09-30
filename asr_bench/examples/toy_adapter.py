"""TEST FIXTURE ONLY: a toy DatasetAdapter (source "toy") and a toy noise source ("toynoise"),
used to exercise ingest -> split -> freeze -> run -> report end to end. No real data."""
from __future__ import annotations

from asr_bench.adapters import DatasetAdapter, SourceInfo, SourceUtterance

TOY_SOURCE = SourceInfo("toy", "0", "toy (test fixture)", "train_ok")
NOISE_SOURCE = SourceInfo("toynoise", "0", "toy noise (test fixture)", "eval_only")
N_SPEAKERS = 30

# (reference, language_primary, languages_present, is_code_switched, token langs, cmi, keyword, safety tags)
# cmi: fixture values on the 0-100 Das & Gambaeck scale, 100 * (1 - dominant / tagged tokens);
# the scale is this fixture's own recorded choice (P-S1-8), not a benchmark decision.
LINES = [
    ("help me मुझे कोई attack कर रहा है", "hi", ["hi", "en"], True, "en en hi hi en hi hi hi", 37.5, "attack", ["safety_keyword", "intra_sentence_cs"]),
    ("मुझे help नहीं चाहिए", "hi", ["hi", "en"], True, "hi en hi hi", 25.0, None, ["negation"]),
    ("please call the police", "en-IN", ["en-IN"], False, None, None, "police", ["safety_keyword"]),
    ("i will call you later", "en-IN", ["en-IN"], False, None, None, None, None),
]


def utterance(spk: int, k: int) -> SourceUtterance:
    ref, lang, present, cs, tl, cmi, kw, tags = LINES[(spk + k) % len(LINES)]
    tokens = ([{"text": w, "lang": l, "script": None, "start_s": None, "end_s": None} for w, l in zip(ref.split(), tl.split())]
              if tl else None)
    return SourceUtterance(
        source_utt_id=f"{spk:02d}{k}", audio_path=f"{spk:02d}{k}.wav", speaker_id=f"toy:spk{spk:02d}",
        session_id=f"toy:sess{spk:02d}", recording_id=None, transcript_ref=ref, transcript_romanised=None, tokens=tokens,
        language_primary=lang, languages_present=present, is_code_switched=cs, cmi=cmi, script="mixed" if cs else "Latn",
        english_word_script="latin" if "hi" in present else None, provenance="read", environment="quiet",
        condition_device="close", condition_real_or_synthetic="real", aug_recipe=None, seed=None, snr_db=None,
        clipping_ratio=None, overlap=False, overlap_spans=None, overlap_rel_db=None, safety_tags=tags,
        keyword_spans=[{"text": kw, "start_s": 0.0, "end_s": 0.5}] if kw else ([] if tags else None),
        licence=None, use_restriction=None)


class ToyAdapter(DatasetAdapter):
    source = TOY_SOURCE

    def utterances(self):
        for spk in range(N_SPEAKERS):
            for k in range(2):
                yield utterance(spk, k)


class ToyNoiseAdapter(DatasetAdapter):
    """No-speech clips (transcript_ref ""), no speaker: eval_only inventory used as mix noise."""
    source = NOISE_SOURCE

    def utterances(self):
        for i in range(2):
            yield SourceUtterance(
                source_utt_id=f"n{i}", audio_path=f"n{i}.wav", speaker_id=None, session_id=None, recording_id=None,
                transcript_ref="", transcript_romanised=None, tokens=None, language_primary="en", languages_present=["en"],
                is_code_switched=False, cmi=None, script="Latn", english_word_script=None, provenance="unknown",
                environment="traffic", condition_device="unknown", condition_real_or_synthetic="real", aug_recipe=None,
                seed=None, snr_db=None, clipping_ratio=None, overlap=False, overlap_spans=None, overlap_rel_db=None,
                safety_tags=None, keyword_spans=None, licence=None, use_restriction=None)
