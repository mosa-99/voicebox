"""Platform defaults for capture hotkey chords."""

from __future__ import annotations

import sys


MAC_PUSH_TO_TALK = ["MetaRight", "AltGr"]
MAC_TOGGLE_TO_TALK = ["MetaRight", "AltGr", "Space"]
NON_MAC_PUSH_TO_TALK = ["ControlRight", "ShiftRight"]
NON_MAC_TOGGLE_TO_TALK = ["ControlRight", "ShiftRight", "Space"]

# Chords are capped at 6 keys (see CaptureSettingsUpdate).
MAX_CHORD_KEYS = 6

# Modifier families tried, in order, when extending the push-to-talk chord
# into the translate chord. Each entry is (family prefixes, left, right).
_TRANSLATE_MODIFIERS = [
    (("Shift",), "ShiftLeft", "ShiftRight"),
    (("Alt",), "Alt", "AltGr"),
    (("Control",), "ControlLeft", "ControlRight"),
]


def default_push_to_talk_chord() -> list[str]:
    if sys.platform == "darwin":
        return MAC_PUSH_TO_TALK.copy()
    return NON_MAC_PUSH_TO_TALK.copy()


def default_toggle_to_talk_chord() -> list[str]:
    if sys.platform == "darwin":
        return MAC_TOGGLE_TO_TALK.copy()
    return NON_MAC_TOGGLE_TO_TALK.copy()


def default_translate_chord(push_to_talk: list[str] | None = None) -> list[str]:
    """The push-to-talk chord plus Shift: hold the dictation keys with Shift
    to dictate and translate.

    The added key sits on the same side as the chord's modifiers. A chord
    that already holds Shift gets Option/Alt instead, then Control.
    """
    push = list(push_to_talk or default_push_to_talk_chord())
    right_handed = any(k.endswith("Right") or k == "AltGr" for k in push)
    for prefixes, left, right in _TRANSLATE_MODIFIERS:
        if any(k.startswith(prefixes) for k in push):
            continue
        if len(push) >= MAX_CHORD_KEYS:
            break
        return [*push, right if right_handed else left]
    # Nothing left to add (or the chord is full): extend the platform
    # default instead, which always has a free modifier family.
    return default_translate_chord(default_push_to_talk_chord())
