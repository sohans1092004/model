"""Telugu / Tamil / Kannada matching rules on top of udk_engine.match_transcript (which stays shared, unchanged):

1. Exact or fuzzy only. Without a semantic matcher, match_transcript falls back to a loose word-overlap score
   (layer "semantic"); NO_SEMANTIC switches that off. Measured (indic_exact_test, TTS): it caused 13 of 24
   near-miss asks ("I am safe" ~ "I'm not safe") and gave 34 of 263 phrase catches.
2. Benign-context cues: a match is dropped when the transcript contains a cue word of a safe or non-urgent reading
   that the matched phrase itself does not contain -- reassurance ("I am safe", "no need", "fine", "don't be
   afraid"), a reported past event ("yesterday", "said"), a question about others, a later time ("evening",
   "tomorrow"). Substring check, so "தேவையில்லை" (no need) blocks but UDK_05's own "தேவை" (need) does not.
   Whole expressions ("I am safe", "she said"), not bare verb forms: on real Telugu recordings "చెప్ప" also blocked
   "tell me" (చెప్పు) and "ఉన్నాను" also blocked "I am waiting" (వేచి ఉన్నాను), each next to a real phrase.
   ponytail: a fixed word list chosen while looking at the near-miss set (so its numbers are optimistic) and
   written by Claude -- needs a native-speaker review and fresh near-miss sentences; a cue said anywhere in the
   same speech segment also drops a real phrase.
"""
from __future__ import annotations

CUES: dict[str, tuple[str, ...]] = {
    "te": ("సురక్షితంగా ఉన్నాను", "సురక్షితంగా ఉన్నారా", "అవసరం లేదు", "బాగానే", "భయపడకు", "నిన్న",
           "చెప్పింది", "చెప్పాడు", "చెప్పారు", "సాయంత్రం", "రేపు"),
    "ta": ("பாதுகாப்பாக இருக்கிறேன்", "பாதுகாப்பாக இருக்கிறார்களா", "தேவையில்லை", "சரியாக", "பயப்படாதே", "நேற்று",
           "சொன்னாள்", "சொன்னான்", "சொன்னார்", "மாலை", "நாளை"),
    "kn": ("ಸುರಕ್ಷಿತವಾಗಿದ್ದ", "ಅಗತ್ಯವಿಲ್ಲ", "ಚೆನ್ನಾಗಿದೆ", "ಭಯಪಡಬೇಡ", "ನಿನ್ನೆ", "ಹೇಳಿದಳು", "ಹೇಳಿದನು", "ಹೇಳಿದರು",
           "ಸಂಜೆ", "ನಾಳೆ"),
}


class _NoSemantic:
    """Passed as match_transcript's semantic_matcher: never matches, keeps the default fuzzy gate (0.55)."""
    threshold, fuzzy_threshold = 2.0, 0.55

    def similarity(self, a: str, b: str) -> float:
        return 0.0


NO_SEMANTIC = _NoSemantic()


MIN_PHRASE_COVERAGE = 0.5


def phrase_coverage(text: str, phrase: str) -> float:
    """Share of the phrase's words heard in `text` (fuzzy word match, ratio >= 75). A te/ta/kn match needs at least
    MIN_PHRASE_COVERAGE: match_transcript also accepts a short transcript that is a fragment of a phrase, and on real
    Telugu TV speech transcribed as Tamil the 2-word 'அது போக' matched the 5-word UDK_18. Measured: real Telugu cries
    10/10 kept; YouTube tune asks 2 -> 1; TTS catches te 78->76, ta 81->78, kn 70->69."""
    from rapidfuzz import fuzz
    from udk_engine import _normalize

    pw, tw = _normalize(phrase).split(), _normalize(text).split()
    return sum(any(fuzz.ratio(w, x) >= 75 for x in tw) for w in pw) / max(len(pw), 1)


def exact_phrase(text: str, udks):
    """The phrase said word for word in `text` (match_transcript's exact layer, not a lone fragment: >= half the
    phrase's words), or None. Used by the Hindi system, where IndicConformer is accurate enough for exact-only."""
    from udk_engine import TRIGGER_VERIFY_THRESHOLD, match_transcript

    m = match_transcript(text, udks, semantic_matcher=NO_SEMANTIC)
    ok = (m.udk is not None and m.layer == "exact" and m.confidence >= TRIGGER_VERIFY_THRESHOLD
          and phrase_coverage(text, m.udk.phrase) >= MIN_PHRASE_COVERAGE)
    return m.udk if ok else None


def benign_cue(text: str, phrase: str, lang: str) -> str | None:
    """The first cue word in `text` that the matched `phrase` lacks, or None."""
    return next((c for c in CUES.get(lang, ()) if c in text and c not in phrase), None)


if __name__ == "__main__":  # self-check
    assert benign_cue("நான் பாதுகாப்பாக இருக்கிறேன் பயப்படாதே", "நான் பாதுகாப்பாக இல்லை", "ta") == "பாதுகாப்பாக இருக்கிறேன்"
    assert benign_cue("దయచేసి సహాయం కోసం కాల్ చేయండి నాకు ఒకసారి చెప్పు", "దయచేసి సహాయం కోసం కాల్ చేయండి", "te") is None
    assert benign_cue("వేచి ఉన్నాను నేను ఇక్కడి నుండి బయటపడాలి", "నేను ఇక్కడ నుండి బయటపడాలి", "te") is None
    assert benign_cue("நான் ஆபத்தில் இருக்கிறேன்", "நான் ஆபத்தில் இருக்கிறேன்", "ta") is None  # the phrase's own word
    assert benign_cue("எனக்கு இப்போதே உதவி தேவை", "எனக்கு இப்போதே உதவி தேவை", "ta") is None
    assert benign_cue("போலீசை அழைக்கத் தேவையில்லை", "எனக்கு இப்போதே உதவி தேவை", "ta") == "தேவையில்லை"
    assert NO_SEMANTIC.similarity("a", "a") < NO_SEMANTIC.threshold
    assert phrase_coverage("அது போக", "எனக்கு இப்போதே வீட்டிற்குப் போக வேண்டும்") < MIN_PHRASE_COVERAGE
    assert phrase_coverage("దయచేసి ఎవరైనా సహాయం చేయండి", "దయచేసి నాకు సహాయం చేయండి") >= MIN_PHRASE_COVERAGE
    from udks import general_udks
    hi = general_udks("hi")
    assert exact_phrase("हेलो प्रिया सुन फोन मत काटना कोई मेरा पीछा कर रहा है मेट्रो से", hi).udk_id == "UDK_04"
    assert exact_phrase("नहीं", hi) is None  # a lone word of a phrase is not the phrase
    assert exact_phrase("मुझे अकेला छोड़ दो गाइज", hi) is None  # fuzzy-only ('leave me alone' to friends)
    print("indic_exact self-check OK")
