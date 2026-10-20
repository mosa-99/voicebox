"""Spoken dictation commands ("neue Zeile", "new paragraph", "سطر جديد",
"Fragezeichen" …) and the line breaks they produce surviving refinement
and translation."""

import pytest

from backend.services import refinement, translation
from backend.services.refinement import RefinementFlags, collapse_repetitive_artifacts
from backend.services.voice_commands import COMMANDS, apply_voice_commands, command_table


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        # Whisper output for spoken test dictations (say + Whisper turbo).
        (
            "Hallo Thomas neue Zeile ich wollte fragen ob du morgen Zeit hast neuer Absatz viele Grüße Mohammed.",
            "Hallo Thomas\nIch wollte fragen ob du morgen Zeit hast.\n\nViele Grüße Mohammed.",
        ),
        (
            "Hallo Thomas, neue Zeile, ich wollte fragen, ob du morgen Zeit hast. Neuer Absatz, viele Grüße, Mohammed.",
            "Hallo Thomas,\nich wollte fragen, ob du morgen Zeit hast.\n\nViele Grüße, Mohammed.",
        ),
        (
            "Kannst du mir morgen helfen? Fragezeichen ich warte auf deine Antwort.",
            "Kannst du mir morgen helfen? Ich warte auf deine Antwort.",
        ),
        (
            "Das Treffen ist um 10 Uhr, danach essen wir zusammen Ausrufezeichen.",
            "Das Treffen ist um 10 Uhr, danach essen wir zusammen!",
        ),
        (
            "Hi Sarah, new line, thanks for your message, new paragraph, best regards, Mohammed.",
            "Hi Sarah,\nThanks for your message.\n\nBest regards, Mohammed.",
        ),
        (
            "Can you send me the file question mark I need it today period",
            "Can you send me the file? I need it today.",
        ),
        (
            "مرحبا أحمد، سطر جديد، أردت أن أسألك عن الموعد، فقرة جديدة، مع تحياتي، محمد",
            "مرحبا أحمد،\nأردت أن أسألك عن الموعد.\n\nمع تحياتي، محمد",
        ),
        ("هل أنت متاح غدا علامة استفهام", "هل أنت متاح غدا؟"),
        ("رائع علامة تعجب شكرا لك فاصلة منقوطة", "رائع! شكرا لك؛"),
        # Lists and a leading break.
        ("Einkaufsliste Doppelpunkt neue Zeile Äpfel neue Zeile Birnen", "Einkaufsliste:\nÄpfel\nBirnen"),
        ("Neue Zeile. Das steht ganz oben.", "\nDas steht ganz oben."),
        ("Das Meeting ist um zehn Uhr Punkt", "Das Meeting ist um zehn Uhr."),
        ("Erster Absatz neuer Absatz neuer Absatz zweiter Absatz", "Erster Absatz.\n\nZweiter Absatz"),
        ("Bis morgen neuer Absatz", "Bis morgen.\n\n"),
    ],
)
def test_commands_become_layout_and_punctuation(transcript, expected):
    assert apply_voice_commands(transcript) == expected


@pytest.mark.parametrize(
    "transcript",
    [
        # The same words as content.
        "Bitte füge in der Tabelle eine neue Zeile für den Monat März hinzu.",
        "Schreib das in die nächste Zeile.",
        "We launched a new line of products last year.",
        "Add a new paragraph about pricing.",
        "Das ist genau der Punkt, den ich meine.",
        "Das ist ein guter Punkt.",
        "Um Punkt zehn Uhr fängt es an.",
        "Der Wert ist zwei Komma fünf Prozent.",
        "It was a long period.",
        "The trial period ended in May.",
        "هذه نقطة مهمة جدا",
        "اكتب هذا في سطر جديد",
        "Hinter dem Plan steht ein Fragezeichen.",
        # No commands at all.
        "Ich komme morgen etwas später.",
        "",
    ],
)
def test_content_is_left_alone(transcript):
    assert apply_voice_commands(transcript) == transcript


def test_command_table_lists_every_command_in_three_languages():
    table = command_table()
    assert [row["action"] for row in table] == [c.action for c in COMMANDS]
    for row in table:
        assert set(row["phrases"]) == {"de", "en", "ar"}


def test_collapse_keeps_line_breaks():
    text = "Hallo URL URL URL URL URL URL Thomas\n\nViele Grüße"
    assert collapse_repetitive_artifacts(text) == "Hallo Thomas\n\nViele Grüße"


class _FakeBackend:
    model_size = "4B"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts: list[str] = []
        self.systems: list[str] = []

    async def generate(self, *, prompt, system, **_):
        self.prompts.append(prompt)
        self.systems.append(system)
        return self.replies.pop(0)


async def test_refinement_keeps_dictated_lines(monkeypatch):
    backend = _FakeBackend(["Hallo Thomas,\nich komme morgen.\n\nViele Grüße"])
    monkeypatch.setattr(refinement.llm_service, "get_llm_model", lambda: backend)

    text, _ = await refinement.refine_transcript(
        "Hallo Thomas,\näh ich komme morgen\n\nViele Grüße", RefinementFlags()
    )

    assert text == "Hallo Thomas,\nich komme morgen.\n\nViele Grüße"
    assert "Keep every line break" in backend.systems[0]


async def test_markdown_hard_breaks_are_tidied(monkeypatch):
    backend = _FakeBackend(["Hallo Thomas,  \nich komme morgen.  \n\nViele Grüße"])
    monkeypatch.setattr(refinement.llm_service, "get_llm_model", lambda: backend)

    text, _ = await refinement.refine_transcript(
        "Hallo Thomas,\nich komme morgen\n\nViele Grüße", RefinementFlags()
    )

    assert text == "Hallo Thomas,\nich komme morgen.\n\nViele Grüße"


async def test_refinement_goes_line_by_line_when_lines_get_merged(monkeypatch):
    backend = _FakeBackend(
        ["Hallo Thomas, ich komme morgen. Viele Grüße", "Hallo Thomas,", "Ich komme morgen.", "Viele Grüße"]
    )
    monkeypatch.setattr(refinement.llm_service, "get_llm_model", lambda: backend)

    text, _ = await refinement.refine_transcript(
        "Hallo Thomas,\näh ich komme morgen\n\nViele Grüße", RefinementFlags()
    )

    assert text == "Hallo Thomas,\nIch komme morgen.\n\nViele Grüße"
    assert backend.prompts[1:] == ["Hallo Thomas,", "äh ich komme morgen", "Viele Grüße"]


async def test_refinement_keeps_a_leading_line_break(monkeypatch):
    backend = _FakeBackend(["Das steht oben."])
    monkeypatch.setattr(refinement.llm_service, "get_llm_model", lambda: backend)

    text, _ = await refinement.refine_transcript("\ndas steht oben", RefinementFlags())

    assert text == "\nDas steht oben."


async def test_translation_goes_line_by_line_when_lines_get_merged(monkeypatch):
    backend = _FakeBackend(["Hello Thomas, I'm coming tomorrow.", "Hello Thomas,", "I'm coming tomorrow."])
    monkeypatch.setattr(translation.llm_service, "get_llm_model", lambda: backend)

    text, _, used = await translation.translate_transcript("Hallo Thomas,\nich komme morgen.", "en")

    assert (text, used) == ("Hello Thomas,\nI'm coming tomorrow.", "en")
    assert "Keep every line break" in backend.systems[0]


def test_spoken_target_language():
    assert translation.spoken_target_language("Ich komme morgen, übersetze das auf Arabisch.") == "ar"
    assert translation.spoken_target_language("Ich komme morgen.") is None
