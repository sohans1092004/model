"""Text normalisation for every Phase 2A §5 metric (stage S4).

§5: "lower-case Latin, Unicode NFC for Indic scripts, punctuation removed, numbers as words".
  - NFC, then str.lower() (a no-op on Indic scripts).
  - Apostrophes are removed ("don't" -> "dont"); every other Unicode punctuation character (P*)
    becomes a space. Symbols (S*) are kept: §5 names punctuation only.
  - Numbers as words: only for English utterances (language_primary "en*"), cardinal integers
    written with ASCII digits. Hindi/Telugu number words are Q9 (open): digits there are left as
    they are and counted (`numbers_left_as_digits`) so reports can show the gap.
The normaliser is fixed configuration, recorded by NORMALISER_VERSION in every report (§6.3).
"""
from __future__ import annotations

import re
import unicodedata

NORMALISER_VERSION = "asr_bench.textnorm/1"
_APOSTROPHES = {"'", "’", "ʼ"}
_DIGITS = re.compile(r"^[0-9]+$")

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def english_number_words(n: int) -> list[str]:
    """Cardinal words for 0 <= n < 10**12, e.g. 2105 -> two thousand one hundred five."""
    if n < 20:
        return [_ONES[n]]
    if n < 100:
        return [_TENS[n // 10]] + ([_ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [_ONES[n // 100], "hundred"] + (english_number_words(n % 100) if n % 100 else [])
    for size, word in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= size:
            return english_number_words(n // size) + [word] + (english_number_words(n % size) if n % size else [])
    raise ValueError(n)


def normalise(text: str, language: str | None = None) -> tuple[list[str], int]:
    """(words, number of digit tokens left unconverted)."""
    text = unicodedata.normalize("NFC", text or "").lower()
    out = []
    for ch in text:
        if ch in _APOSTROPHES:
            continue
        out.append(" " if unicodedata.category(ch).startswith("P") else ch)
    words, left = [], 0
    english = (language or "").split("-")[0] == "en"
    for w in "".join(out).split():
        if _DIGITS.match(w):
            if english and len(w) <= 12:
                words.extend(english_number_words(int(w)))
                continue
            left += 1
        words.append(w)
    return words, left


_SCRIPT_BY_NAME = {"LATIN": "Latn", "DEVANAGARI": "Deva", "TELUGU": "Telu", "BENGALI": "Beng", "TAMIL": "Taml",
                   "KANNADA": "Knda", "MALAYALAM": "Mlym", "GUJARATI": "Gujr", "GURMUKHI": "Guru", "ORIYA": "Orya"}


def word_script(word: str) -> str | None:
    """ISO 15924 code of the first letter in `word`, or None."""
    for ch in word:
        if unicodedata.category(ch).startswith("L"):
            name = unicodedata.name(ch, "")
            return _SCRIPT_BY_NAME.get(name.split(" ")[0])
    return None
