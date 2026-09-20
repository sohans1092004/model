"""
Multilingual support checks (English/Hindi/Telugu/Kannada/Tamil, added on
request -- see udks.py's module docstring for the full real-evidence
story: a real bug found in _normalize() that would have corrupted every
non-Latin-script phrase, and a real finding that the English semantic
model doesn't meaningfully work for Telugu/Kannada/Tamil at all).

Fast and portable -- exact-match/API-wiring checks only, no real STT/
audio. The real per-language semantic-matcher calibration (LaBSE, 200
negative pairs per language) and the _normalize() Unicode-category fix
were verified manually this session with real numbers (see README.md),
same treatment kws.py's/semantic.py's other real backends already got.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import api
from udk_engine import _normalize, match_transcript
from udks import SUPPORTED_LANGUAGES, _UDK_TABLE, general_udks

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name} {detail}")


print("=== _normalize() preserves Unicode combining marks (real bug, fixed) ===")

# "मुझे" (Hindi "mujhe", = "me") -- the old \w-based regex stripped both
# vowel signs, turning this into the different/meaningless "मझ".
check("Hindi combining marks survive normalization", _normalize("मुझे मदद चाहिए!") == "मुझे मदद चाहिए")
check("Telugu combining marks survive normalization", _normalize("నాకు సహాయం కావాలి!") == "నాకు సహాయం కావాలి")
check("Kannada combining marks survive normalization", _normalize("ನನಗೆ ಸಹಾಯ ಬೇಕು!") == "ನನಗೆ ಸಹಾಯ ಬೇಕು")
check("Tamil combining marks survive normalization", _normalize("எனக்கு உதவி வேண்டும்!") == "எனக்கு உதவி வேண்டும்")
check("English punctuation stripping unchanged", _normalize("Help me, please!") == "help me please")
check("English contractions unchanged (apostrophe still stripped)", _normalize("he's going to hurt me") == "hes going to hurt me")

print(f"\n{passed}/{passed + failed} checks passed so far.\n")

print("=== Exact-match layer works correctly for every supported language ===")

for lang in SUPPORTED_LANGUAGES:
    udks = general_udks(lang)
    all_ok = all(
        (result := match_transcript(udk.phrase, udks)).udk is not None
        and result.udk.udk_id == udk.udk_id
        and result.layer == "exact"
        and result.confidence == 1.0
        for udk in udks
    )
    check(f"all {len(udks)} UDKs exact-self-match correctly in {lang!r}", all_ok, lang)

print(f"\n{passed}/{passed + failed} checks passed so far.\n")

print("=== Live API: language selection wiring ===")

client = TestClient(api.app, headers={"X-Service-Token": api.DEV_SERVICE_TOKEN})

resp = client.post("/v1/journeys/start", json={"user_id": "U_multilingual_test", "language": "hi"})
check("Hindi journey starts successfully (200)", resp.status_code == 200, str(resp.text))
if resp.status_code == 200:
    journey = api._store.get(resp.json()["journey_id"])
    check("journey.language is 'hi'", journey.language == "hi", journey.language)
    check(
        "journey's engine is enrolled with Hindi UDKs, not English",
        all(u.language == "hi" for u in journey.engine.udks if u.udk_type == "GENERAL"),
        str({u.udk_id: u.language for u in journey.engine.udks}),
    )
    hindi_udk08 = _UDK_TABLE["hi"]["UDK_08"][0]
    decision = journey.engine.decide(hindi_udk08, now_s=0.0)
    check(
        "a real Hindi UDK phrase (UDK_08 equivalent) triggers correctly",
        decision.udk is not None and decision.udk.udk_id == "UDK_08" and decision.decision != "NO_ACTION",
        str(decision),
    )

resp_bad = client.post("/v1/journeys/start", json={"user_id": "U_bad_lang_test", "language": "fr"})
check("an unsupported language is rejected with 400, not silently defaulted", resp_bad.status_code == 400, str(resp_bad.text))

resp_default = client.post("/v1/journeys/start", json={"user_id": "U_default_lang_test"})
check("omitting language still works and defaults to English (backward compat)", resp_default.status_code == 200, str(resp_default.text))
if resp_default.status_code == 200:
    default_journey = api._store.get(resp_default.json()["journey_id"])
    check("default journey.language is 'en'", default_journey.language == "en", default_journey.language)

print(f"\n{passed}/{passed + failed} checks passed so far.\n")

print("=== create_or_get selects the right STT backend per language (fake backends, no real model load) ===")


class FakeTeluguSTT:
    model_version = "fake-telugu-stt"

    def transcribe(self, pcm):
        raise NotImplementedError  # never actually called in this check


fake_te_stt = FakeTeluguSTT()
default_stt = api.MockSTT()
telugu_journey, _ = api._store.create_or_get(
    "J_telugu_stt_test", "U_telugu_stt_test", default_stt, api.SAMPLE_PERSONAL_UDK, language="te", stt_by_language={"te": fake_te_stt}
)
check("a language with a real entry in stt_by_language gets that backend, not the default", telugu_journey.stt is fake_te_stt)

kannada_journey, _ = api._store.create_or_get(
    "J_kannada_stt_test", "U_kannada_stt_test", default_stt, api.SAMPLE_PERSONAL_UDK, language="kn", stt_by_language={"te": fake_te_stt}
)
check("a language with NO entry in stt_by_language falls back to the default stt backend", kannada_journey.stt is default_stt)

no_override_journey, _ = api._store.create_or_get(
    "J_no_override_stt_test", "U_no_override_stt_test", default_stt, api.SAMPLE_PERSONAL_UDK, language="te"
)
check("stt_by_language omitted entirely (backward compat) -- default constructor value is used, not an error", no_override_journey.stt is default_stt)

print(f"\n{passed}/{passed + failed} checks passed so far.\n")

print("=== create_or_get selects the right KWS backend per language (fake backends, no real model load) ===")


class FakeTeluguKWS:
    model_version = "fake-telugu-kws"

    def enroll(self, phrase_id, pcm):
        raise NotImplementedError

    def spot(self, pcm):
        raise NotImplementedError

    def clear(self, phrase_id):
        raise NotImplementedError


fake_te_kws = FakeTeluguKWS()
telugu_kws_journey, _ = api._store.create_or_get(
    "J_telugu_kws_test", "U_telugu_kws_test", default_stt, api.SAMPLE_PERSONAL_UDK, language="te", kws_by_language={"te": fake_te_kws}
)
check("a language with a real entry in kws_by_language gets that backend, not the default (None)", telugu_kws_journey.kws is fake_te_kws)

kannada_kws_journey, _ = api._store.create_or_get(
    "J_kannada_kws_test", "U_kannada_kws_test", default_stt, api.SAMPLE_PERSONAL_UDK, language="kn", kws_by_language={"te": fake_te_kws}
)
check("a language with NO entry in kws_by_language falls back to the default (None -- KWS off)", kannada_kws_journey.kws is None)

print(f"\n{'=' * 40}\n{passed}/{passed + failed} TOTAL PASSED" + (" -- ALL PASSED" if failed == 0 else f", {failed} FAILED"))

if failed:
    raise SystemExit(1)
