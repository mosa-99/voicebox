# Arabic words and typographic quotes are matched on purpose.
# ruff: noqa: RUF001
"""
Spoken translation instructions — lets the speaker pick the target language
by saying it, e.g. "ترجم الجملة الآتية إلى اللغة الألمانية …", "Translate
this into Arabic: …" or "…, übersetze das auf Arabisch".

The translate shortcut would otherwise translate the instruction along with
the content ("Translate the following sentence into German: …"). This finds
an instruction at the start or end of the transcript, returns the language
it names and the transcript without it. Whisper rarely punctuates Arabic, so
the instruction's end is found from the words themselves: the language name
after a "to / in / إلى / باللغة" style preposition.

Only English, German and Arabic phrasings are recognised — the languages
the translate shortcut is used with.
"""

import re

# Characters stripped from a word's edges before matching.
_EDGE_PUNCTUATION = "\"'“”„«»‚‘’()[]{}:;,.!?…،؛؟-–—"
_ARABIC_DIACRITICS = re.compile(r"[ً-ٰٟـ]")

# German names take the usual adjective endings ("ins Arabische",
# "auf Englisch", "in die deutsche Sprache").
_GERMAN_ENDINGS = ("", "e", "en", "er", "es")
_LATIN_NAMES: dict[str, str] = {}
for _code, _english, _german_stems in [
    ("en", "english", ("englisch",)),
    ("de", "german", ("deutsch",)),
    ("ar", "arabic", ("arabisch",)),
    ("fr", "french", ("französisch", "franzoesisch", "franzosisch")),
    ("es", "spanish", ("spanisch",)),
    ("ja", "japanese", ("japanisch",)),
    ("zh", "chinese", ("chinesisch",)),
    ("hi", "hindi", ("hindi",)),
]:
    _LATIN_NAMES[_english] = _code
    for _stem in _german_stems:
        for _ending in _GERMAN_ENDINGS:
            _LATIN_NAMES[_stem + _ending] = _code

# Arabic names after normalisation (see ``_normalize``), without the article
# or a ب/ل/و prefix, which ``_arabic_language`` strips.
_ARABIC_NAMES: dict[str, str] = {
    "انجليزيه": "en", "انجليزي": "en", "انكليزيه": "en", "انكليزي": "en",
    "المانيه": "de", "الماني": "de",
    "عربيه": "ar", "عربي": "ar",
    "فرنسيه": "fr", "فرنسي": "fr",
    "اسبانيه": "es", "اسباني": "es",
    "يابانيه": "ja", "ياباني": "ja",
    "صينيه": "zh", "صيني": "zh",
    "هنديه": "hi", "هندي": "hi",
}  # fmt: skip
_ARABIC_PREFIXES = ("وبال", "بال", "لل", "وال", "فال", "ال", "ب", "ل", "و")

# Words that lead into the language name: "into German", "auf Arabisch",
# "ins Englische", "إلى اللغة الألمانية", "باللغة الألمانية".
_PREPOSITIONS = {"to", "into", "in", "auf", "ins", "nach", "zu", "zum", "الي"}
# Words that may sit between the preposition and the name; the Arabic ones
# carry the preposition themselves ("باللغة الألمانية").
_NAME_LEAD_INS = {"the", "die", "das", "den", "dem", "اللغه", "لغه"}
_PREPOSITION_LEAD_INS = {"باللغه", "للغه", "بلغه"}
# Politeness and filler, allowed before the verb, around the language name
# and in front of an instruction at the end.
_FILLER_PHRASES = [
    ("من", "فضلك"), ("لو", "سمحت"),
    ("please",), ("bitte",), ("also",), ("ok",), ("okay",), ("ähm",), ("äh",), ("um",), ("uh",),
    ("hey",), ("now",), ("jetzt",), ("mal",), ("رجاء",), ("رجاءا",), ("يرجي",),
    ("اممم",), ("امم",), ("طيب",), ("language",), ("sprache",),
]  # fmt: skip
# What "translate …" names when no language follows; the instruction ends
# after the longest match.
_OBJECT_PHRASES = sorted(
    [
        ("the", "following", "sentence"), ("the", "following", "text"), ("the", "following"),
        ("this", "sentence"), ("this", "text"), ("this",), ("that",), ("it",),
        ("den", "folgenden", "satz"), ("den", "folgenden", "text"), ("folgenden", "satz"),
        ("folgenden", "text"), ("folgendes",), ("diesen", "satz"), ("das",), ("dies",), ("es",),
        ("الجمله", "الاتيه"), ("الجمله", "التاليه"), ("النص", "الاتي"), ("النص", "التالي"),
        ("هذه", "الجمله"), ("هذا", "النص"), ("الجمله",), ("هذا",), ("هذه",),
    ],
    key=len,
    reverse=True,
)  # fmt: skip
# Words allowed between the verb and the language name ("translate this for
# me into German", "übersetz mir das bitte ins Englische", "ترجم لي هذا إلى
# الألمانية"). Anything else means the name belongs to the content.
_INSTRUCTION_WORDS = (
    {word for phrase in _OBJECT_PHRASES for word in phrase}
    | {word for phrase in _FILLER_PHRASES for word in phrase}
    | _PREPOSITIONS
    | _NAME_LEAD_INS
    | _PREPOSITION_LEAD_INS
    | {"for", "me", "mir", "uns", "doch", "kurz", "schnell", "لي", "لنا"}
    # The source language: "from German into English", "von Arabisch auf Deutsch".
    | {"from", "von", "aus", "من"}
)
_FILLER_WORDS = {word for phrase in _FILLER_PHRASES for word in phrase}
# Allowed in front of an instruction verb at the end ("…, and then translate
# it to …", "… Kannst du das bitte auf Arabisch übersetzen?").
_CONNECTORS = {"and", "then", "can", "you", "could", "und", "dann", "kannst", "könntest", "du", "ثم"}

# How far apart the verb and the language name may be, in words.
_MAX_INSTRUCTION_WORDS = 8


def _normalize(word: str) -> str:
    word = word.strip(_EDGE_PUNCTUATION).lower()
    word = _ARABIC_DIACRITICS.sub("", word)
    return (
        word.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ة", "ه").replace("ى", "ي")
    )  # fmt: skip


def _arabic_language(word: str) -> tuple[str | None, bool]:
    """(language code, whether a ب/ل prefix — "in"/"to" — was attached)."""
    if word in _ARABIC_NAMES:
        return _ARABIC_NAMES[word], False
    for prefix in _ARABIC_PREFIXES:
        rest = word[len(prefix):]
        if word.startswith(prefix) and len(rest) >= 3 and rest in _ARABIC_NAMES:
            return _ARABIC_NAMES[rest], prefix in ("وبال", "بال", "لل", "ب", "ل")
    return None, False


def _is_verb(word: str) -> bool:
    if word.startswith(("translat", "übersetz", "uebersetz")):
        return True
    return word.lstrip("وف").startswith(("ترجم", "اترجم"))


class _Words:
    def __init__(self, text: str):
        self.text = text
        self.spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        self.norm = [_normalize(text[a:b]) for a, b in self.spans]

    def __len__(self) -> int:
        return len(self.norm)

    def is_language(self, i: int) -> bool:
        word = self.norm[i]
        return word in _LATIN_NAMES or _arabic_language(word)[0] is not None

    def target_at(self, i: int) -> str | None:
        """The language named by word ``i`` when it reads as a target
        ("into German", "auf Arabisch", "باللغة الألمانية", "بالعربي")."""
        word = self.norm[i]
        code = _LATIN_NAMES.get(word)
        prefixed = False
        if code is None:
            code, prefixed = _arabic_language(word)
        if code is None:
            return None
        if prefixed:
            return code
        j = i - 1
        while j >= 0 and i - j <= 2 and self.norm[j] in _NAME_LEAD_INS:
            if self.norm[j] in {"اللغه", "لغه"} and j >= 1 and self.norm[j - 1] == "الي":
                return code
            j -= 1
        if j >= 0 and (self.norm[j] in _PREPOSITIONS or self.norm[j] in _PREPOSITION_LEAD_INS):
            return code
        return None

    def filler_len(self, i: int) -> int:
        """Number of words forming a filler phrase at ``i`` (0 if none)."""
        for phrase in _FILLER_PHRASES:
            if tuple(self.norm[i : i + len(phrase)]) == phrase:
                return len(phrase)
        return 0

    def ends_clause(self, i: int, *, comma: bool = False) -> bool:
        marks = ":.!?،؛؟;" + ("," if comma else "")
        return self.text[self.spans[i][1] - 1] in marks

    def before(self, i: int) -> str:
        return self.text[: self.spans[i][0]] if i < len(self) else self.text

    def after(self, i: int) -> str:
        return self.text[self.spans[i][0]:] if i < len(self) else ""


def _clean(content: str) -> str:
    quotes = "\"'“”„«»‚‘’"
    content = content.strip().strip(quotes).strip(" :,،;؛-–—").strip().strip(quotes)
    return content.strip()


def _target_after_verb(words: _Words, verb: int, stop: int) -> int | None:
    """Index of the target language name following ``verb`` with only
    instruction words (or a source language) in between, searching up to
    ``stop`` (exclusive). The last target wins: "from Arabic into English"."""
    found = None
    for j in range(verb + 1, min(verb + 1 + _MAX_INSTRUCTION_WORDS, stop)):
        if words.target_at(j):
            found = j
        elif words.norm[j] not in _INSTRUCTION_WORDS and not words.is_language(j):
            break
        if words.ends_clause(j):
            break
    return found


def _instruction_at_start(words: _Words) -> tuple[str | None, int] | None:
    """(target or None, index of the first content word)."""
    i = 0
    while i < len(words) and i < 3 and words.filler_len(i):
        i += words.filler_len(i)
    if i < len(words) and _is_verb(words.norm[i]):
        verb = i
        name = _target_after_verb(words, verb, len(words))
        if name is not None:
            end = name + 1
            while end < len(words) and words.filler_len(end) and not words.ends_clause(end - 1):
                end += words.filler_len(end)
            return words.target_at(name), end
        # No language named: drop "translate the following sentence" and use
        # the default language.
        for phrase in _OBJECT_PHRASES:
            if tuple(words.norm[verb + 1 : verb + 1 + len(phrase)]) == phrase:
                return None, verb + 1 + len(phrase)
        return None, verb + 1
    # "Auf Arabisch: …" / "In German: …" — no verb, but a colon.
    for j in range(min(4, len(words))):
        if words.ends_clause(j):
            if words.text[words.spans[j][1] - 1] == ":":
                for k in range(j + 1):
                    if words.target_at(k):
                        return words.target_at(k), j + 1
            break
    return None


def _extend_back(words: _Words, start: int, allowed: set[str]) -> int:
    """Move ``start`` back over ``allowed`` words without crossing a clause."""
    while start > 0 and words.norm[start - 1] in allowed and not words.ends_clause(start - 1, comma=True):
        start -= 1
    return start


def _instruction_at_end(words: _Words) -> tuple[str, int] | None:
    """(target, index of the first instruction word)."""
    last = len(words) - 1
    while last > 0 and words.norm[last] in _FILLER_WORDS:
        last -= 1
    if last < 1:
        return None
    # "…, übersetze das auf Arabisch" / "…, translate it into German"
    target = words.target_at(last)
    if target:
        for verb in range(last - 1, max(-1, last - _MAX_INSTRUCTION_WORDS - 1), -1):
            if _is_verb(words.norm[verb]):
                if _target_after_verb(words, verb, last + 1) != last:
                    return None
                return target, _extend_back(words, verb, _CONNECTORS | _FILLER_WORDS)
            if words.norm[verb] not in _INSTRUCTION_WORDS:
                return None
    # "… bitte auf Arabisch übersetzen" / "… auf Arabisch übersetzen?"
    if _is_verb(words.norm[last]):
        for j in range(last - 1, max(-1, last - 4), -1):
            target = words.target_at(j)
            if target:
                return target, _extend_back(words, j, _CONNECTORS | _INSTRUCTION_WORDS)
            if words.norm[j] not in _INSTRUCTION_WORDS:
                return None
    return None


def split_translation_instruction(transcript: str) -> tuple[str | None, str]:
    """Split a spoken instruction off the transcript.

    Returns:
        (target language code or None, the transcript without the
        instruction). Without an instruction, ``(None, transcript)``.
    """
    words = _Words(transcript)
    if len(words) < 2:
        return None, transcript

    start = _instruction_at_start(words)
    if start is not None:
        target, content_from = start
        content = _clean(words.after(content_from))
        if content:
            return target, content

    end = _instruction_at_end(words)
    if end is not None:
        target, instruction_from = end
        content = _clean(words.before(instruction_from))
        if content:
            return target, content

    return None, transcript
