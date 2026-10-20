# Arabic words and punctuation are matched on purpose.
# ruff: noqa: RUF001
"""
Spoken dictation commands — "neue Zeile", "new paragraph", "سطر جديد",
"Fragezeichen", "question mark" … become line breaks and punctuation.

Applied to a dictation's transcript right after speech-to-text, so the
pasted text, the refined text and the translation all keep the layout.

Whisper keeps the command words as text, with or without commas around
them ("Hallo Thomas, neue Zeile, ich …" / "Hallo Thomas neue Zeile ich …"),
and the same words also occur as ordinary content ("füge eine neue Zeile
für März hinzu", "a new line of products", "der springende Punkt"). A
command is therefore only taken as one where it can't be part of the
sentence: not right after an article, possessive or preposition, and — for
layout commands — not followed by words that continue the noun ("of",
"für", "في"). Words that are mostly content ("Punkt", "Komma", "period",
"colon", "نقطة") additionally have to end a clause, with no article in the
two words before them ("ein guter Punkt." stays as it is).
"""

import re
from dataclasses import dataclass

from .refinement import _GERMAN_WORDS, _english_share, _word_share


@dataclass(frozen=True)
class VoiceCommand:
    action: str
    # Spoken phrases per language (lowercase).
    phrases: dict[str, tuple[str, ...]]

    @property
    def is_layout(self) -> bool:
        return self.action in ("newline", "paragraph")


COMMANDS: tuple[VoiceCommand, ...] = (
    VoiceCommand(
        "paragraph",
        {
            "de": ("neuer absatz", "nächster absatz", "neuen absatz"),
            "en": ("new paragraph", "next paragraph"),
            "ar": ("فقرة جديدة", "الفقرة التالية", "فقرة تالية"),
        },
    ),
    VoiceCommand(
        "newline",
        {
            "de": ("neue zeile", "nächste zeile", "zeilenumbruch"),
            "en": ("new line", "next line", "newline", "line break"),
            "ar": ("سطر جديد", "السطر التالي", "سطر تالي"),
        },
    ),
    VoiceCommand(
        "question",
        {
            "de": ("fragezeichen",),
            "en": ("question mark",),
            "ar": ("علامة استفهام", "علامة الاستفهام"),
        },
    ),
    VoiceCommand(
        "exclamation",
        {
            "de": ("ausrufezeichen", "ausrufungszeichen"),
            "en": ("exclamation mark", "exclamation point"),
            "ar": ("علامة تعجب", "علامة التعجب"),
        },
    ),
    VoiceCommand(
        "semicolon",
        {"de": ("semikolon", "strichpunkt"), "en": ("semicolon",), "ar": ("فاصلة منقوطة",)},
    ),
    VoiceCommand("colon", {"de": ("doppelpunkt",), "en": ("colon",), "ar": ("نقطتان",)}),
    VoiceCommand("comma", {"de": ("komma",), "en": ("comma",), "ar": ("فاصلة",)}),
    VoiceCommand("period", {"de": ("punkt",), "en": ("period", "full stop"), "ar": ("نقطة",)}),
)

_SYMBOLS = {
    "question": ("?", "؟"),
    "exclamation": ("!", "!"),
    "semicolon": (";", "؛"),
    "colon": (":", ":"),
    "comma": (",", "،"),
    "period": (".", "."),
}
_SENTENCE_END = ".?!؟"
_EDGE_PUNCTUATION = "\"'“”„«»‚‘’()[]{}:;,.!?…،؛؟-–—"
_TRAILING_PUNCTUATION = ".,;:!?…،؛؟"
_ARABIC_DIACRITICS = re.compile(r"[ً-ٰٟـ]")
_ARABIC_LETTER = re.compile(r"[؀-ۿ]")

# Words before a command that make it part of the sentence: "eine neue
# Zeile", "a new line", "der Punkt", "in die nächste Zeile", "في سطر جديد".
_BLOCKERS_BEFORE = frozenset(
    """
    ein eine einen einem einer eines der die das den dem des jede jeder jedes jeden
    diese dieser dieses diesen keine kein keinen meine meinen deine deinen seine ihre
    unsere eure welche welcher welchen in im ins auf zur zum zu pro als
    a an the this that these those every each any no my your his her our their its
    another one in into on at to of per
    في على الي من كل هذا هذه ذلك تلك اي او عن
    """.split()
)
# Words after a layout command that continue the noun: "eine neue Zeile
# für März", "a new line of products", "سطر جديد في الجدول".
_CONTINUATIONS_AFTER = frozenset(
    """
    für in im der des von vom mit zum zur auf pro hinzu einfügen hinzufügen ist war wird
    of for in into to at with from on per is was will that which
    في من على الي عن
    """.split()
)


def _normalize(word: str) -> str:
    word = word.strip(_EDGE_PUNCTUATION).lower()
    word = _ARABIC_DIACRITICS.sub("", word)
    return (
        word.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ة", "ه").replace("ى", "ي")
    )  # fmt: skip


# Mostly content words ("der springende Punkt", "zwei Komma fünf", "a long
# period", "colon cancer", "نقطة مهمة"): commands only at a clause end.
_STRICT_PHRASES = frozenset(
    {("punkt",), ("komma",), ("period",), ("full", "stop"), ("comma",), ("colon",), ("نقطه",), ("فاصله",)}
)

# (normalized phrase words, command), longest phrases first.
_PHRASES: list[tuple[tuple[str, ...], VoiceCommand]] = sorted(
    (
        (tuple(_normalize(w) for w in phrase.split()), command)
        for command in COMMANDS
        for phrases in command.phrases.values()
        for phrase in phrases
    ),
    key=lambda item: len(item[0]),
    reverse=True,
)


def _ends_clause(token: str) -> bool:
    return bool(token) and token[-1] in _TRAILING_PUNCTUATION


@dataclass
class _Match:
    start: int
    length: int
    command: VoiceCommand
    strict: bool


def _blocked(tokens: list[str], norm: list[str], i: int) -> bool:
    """Word ``i`` makes the following command part of the sentence."""
    return not _ends_clause(tokens[i]) and norm[i] in _BLOCKERS_BEFORE


def _find_commands(tokens: list[str], norm: list[str]) -> list[_Match]:
    candidates: list[_Match] = []
    i = 0
    while i < len(tokens):
        for phrase, command in _PHRASES:
            n = len(phrase)
            if tuple(norm[i : i + n]) != phrase:
                continue
            # A phrase must not straddle a clause break ("neue, Zeile").
            if any(_ends_clause(t) for t in tokens[i : i + n - 1]):
                continue
            candidates.append(_Match(i, n, command, phrase in _STRICT_PHRASES))
            i += n - 1
            break
        i += 1

    starts = {m.start for m in candidates}
    accepted: list[_Match] = []
    for m in candidates:
        before = m.start - 1
        after = m.start + m.length
        if before < 0:
            # Nothing to punctuate at the very start; a leading line break is fine.
            if not m.command.is_layout:
                continue
        elif _blocked(tokens, norm, before) or (m.strict and before >= 1 and _blocked(tokens, norm, before - 1)):
            continue
        right_closed = after >= len(tokens) or _ends_clause(tokens[after - 1]) or after in starts
        if not right_closed:
            if m.strict:
                continue
            if m.command.is_layout and norm[after] in _CONTINUATIONS_AFTER:
                continue
        accepted.append(m)
    return accepted


def _capitalize(token: str) -> str:
    for k, ch in enumerate(token):
        if ch.isalpha():
            return token[:k] + ch.upper() + token[k + 1 :] if ch.islower() else token
    return token


def apply_voice_commands(text: str) -> str:
    """Replace spoken commands with line breaks and punctuation.

    Text without commands is returned unchanged.
    """
    tokens = text.split()
    if not tokens:
        return text
    norm = [_normalize(t) for t in tokens]
    matches = _find_commands(tokens, norm)
    if not matches:
        return text

    # After "Hallo Thomas," on a new line German continues in lowercase;
    # English capitalises.
    german = _word_share(text, _GERMAN_WORDS)
    lowercase_after_comma = german >= 0.05 and german > _english_share(text)
    by_start = {m.start: m for m in matches}
    out = ""
    capitalize_next = False
    i = 0
    while i < len(tokens):
        match = by_start.get(i)
        if match is None:
            token = tokens[i]
            if capitalize_next:
                token = _capitalize(token)
                capitalize_next = False
            if out and not out.endswith("\n"):
                out += " "
            out += token
            i += 1
            continue

        i += match.length
        action = match.command.action
        out = out.rstrip(" ")
        if match.command.is_layout:
            if action == "paragraph" and out and not out.endswith("\n"):
                # A paragraph closes its sentence.
                stripped = out.rstrip(",;،؛")
                out = stripped if stripped.endswith(tuple(_SENTENCE_END)) else stripped + "."
            ended = out.rstrip("\n")
            breaks = len(out) - len(ended) + (2 if action == "paragraph" else 1)
            out = ended + "\n" * min(2, breaks)
            capitalize_next = not (ended.endswith(",") and lowercase_after_comma)
        else:
            body = out.rstrip(_TRAILING_PUNCTUATION)
            if not body or body.endswith("\n"):
                continue
            latin, arabic = _SYMBOLS[action]
            out = body + (arabic if _ARABIC_LETTER.search(body[-1]) else latin)
            capitalize_next = out[-1] in _SENTENCE_END
        # Drop punctuation-only tokens Whisper put right after the command.
        while i < len(tokens) and not tokens[i].strip(_EDGE_PUNCTUATION):
            i += 1
    return out.strip(" ")


def command_table() -> list[dict]:
    """The supported commands, for the settings page."""
    return [
        {"action": c.action, "phrases": {lang: list(p) for lang, p in c.phrases.items()}}
        for c in COMMANDS
    ]
