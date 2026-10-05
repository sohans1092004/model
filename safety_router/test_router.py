"""Checks for the pure routing/combining logic (no models). Run: python -m safety_router.test_router"""
from safety_router.hindi import decide
from safety_router.router import SegmentRouter, combine, route

S = ["en", "hi"]
assert route({"en": 0.99, "hi": 0.005}, S) == ["en"]               # clearly English -> English only
assert route({"en": 0.01, "hi": 0.97, "ja": 0.02}, S) == ["hi"]    # unsupported languages don't count
assert route({"en": 0.6, "hi": 0.35}, S) == ["en", "hi"]           # unsure -> both
assert route({}, S) == ["en", "hi"]                                # no signal -> everything (cap)
assert route({"en": 0.4, "hi": 0.3, "te": 0.2, "ta": 0.1}, ["en", "hi", "te", "ta"]) == ["en", "hi", "te"]  # cap 3

assert combine({"en": "none", "hi": "VERIFY"}) == "VERIFY"
assert combine({"en": "ALERT", "hi": "VERIFY"}) == "ALERT"
assert combine({"hi": "none"}, scream_fired=True) == "VERIFY"     # scream counts on every route
assert combine({"hi": "ALERT"}, scream_fired=True) == "ALERT"

assert decide(0.60, 0.9, "मुझे बचाओ") == "ALERT"
assert decide(0.60, 0.1, "मुझे बचाओ") == "VERIFY"
assert decide(0.60, 0.005, "मुझे बचाओ") == "none"                  # [B] near-certain benign -> no ask (TV/phone dialogue)
assert decide(0.50, 0.85, "मुझे बचाओ") == "ALERT"                  # bystander path
assert decide(0.50, 0.75, "मुझे बचाओ") == "none"
assert decide(0.60, 0.9, "आई थिंक इट इज") == "none"               # mostly English -> Hindi system stays quiet

calls = []
r = SegmentRouter({"en": lambda p, s, x: calls.append("en") or "none", "hi": lambda p, s, x: calls.append("hi") or "ALERT"},
                  language_id=lambda pcm: {"en": 0.02, "hi": 0.98}, scream=lambda pcm: False)
res = r.process(b"\x00\x00" * 1600, 0, {})
assert res.final == "ALERT" and res.languages == ["hi"] and calls == ["hi"]  # English system never ran
print("safety_router checks passed")
