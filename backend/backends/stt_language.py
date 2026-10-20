"""
Choosing the transcription language among the languages a user speaks.

Whisper's own detection picks from ~99 languages. On short dictations it can
be confidently wrong: one user's Arabic and German recordings came back as
Icelandic-looking gibberish ("Tessgíl, tegirrað, rákað máginn." for
"تسجيل تجربة رقمها") with Icelandic at 0.95-0.98. Renormalising the
detection over the allowed languages does not help there — English, at
0.01-0.03, still beats Arabic at 0.001.

So when Whisper's top guess is allowed it is used as is. When it is not,
the first window is decoded once in every allowed language and the one the
model reads most confidently wins, skipping decodes that loop.
"""

import logging
import zlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Whisper's own threshold for a decode that is stuck repeating itself.
COMPRESSION_RATIO_THRESHOLD = 2.4


class LanguageTrial(NamedTuple):
    """How well one forced-language decode of the first window went."""

    avg_logprob: float
    compression_ratio: float


def compression_ratio(text: str) -> float:
    """Whisper's repetition measure: how well the text compresses."""
    data = text.encode("utf-8")
    return len(data) / len(zlib.compress(data)) if data else 0.0


def normalize_languages(languages: Iterable[str] | None) -> list[str]:
    """Lower-case, de-duplicated language codes in their original order."""
    seen: list[str] = []
    for code in languages or ():
        code = (code or "").strip().lower()
        if code and code != "auto" and code not in seen:
            seen.append(code)
    return seen


def choose_language(
    probs: Mapping[str, float],
    allowed: Sequence[str],
    trial: Callable[[str], LanguageTrial],
) -> str:
    """Pick the transcription language among ``allowed``.

    Args:
        probs: Whisper's language probabilities for the first window.
        allowed: Language codes the speaker uses (at least one).
        trial: Decodes the first window in the given language.
    """
    top = max(probs, key=probs.get)
    # Codes the model doesn't know can't be decoded; try likelier languages
    # first so ties go to the detector's preference.
    candidates = sorted((c for c in allowed if c in probs), key=lambda c: -probs[c])
    if top in candidates or not candidates:
        logger.info("STT language: %s (detected %.2f)", top, probs[top])
        return top

    trials = {code: trial(code) for code in candidates}
    fluent = [c for c in candidates if trials[c].compression_ratio <= COMPRESSION_RATIO_THRESHOLD]
    chosen = max(fluent or candidates, key=lambda code: trials[code].avg_logprob)
    logger.info(
        "STT language: %s (detected %s %.2f, outside %s; trials %s)",
        chosen,
        top,
        probs[top],
        ",".join(candidates),
        ", ".join(f"{code} {t.avg_logprob:.2f}/{t.compression_ratio:.1f}" for code, t in trials.items()),
    )
    return chosen
