# Arabic words and typographic quotes are matched on purpose.
# ruff: noqa: RUF001
"""Spoken translation instructions: the target language said in the
dictation ("ترجم … إلى اللغة الألمانية", "…, übersetze das auf Arabisch")
overrides the setting and is removed before translating."""

import pytest

from backend.services import translation
from backend.services.translation_instruction import split_translation_instruction


@pytest.mark.parametrize(
    ("transcript", "target", "content"),
    [
        # The user's own dictations (Whisper output, unpunctuated Arabic).
        (
            "ترجم الجملة الآتية إلى اللغة الألمانية البحث عن فرص عمل في ألمانيا",
            "de",
            "البحث عن فرص عمل في ألمانيا",
        ),
        ("ترجم الى اللغة المانية البحث عن فرص عمل", "de", "البحث عن فرص عمل"),
        (
            "ترجم الجملة الآتية باللغة الألمانية البحث عن فرص عمل في ألمانيا",
            "de",
            "البحث عن فرص عمل في ألمانيا",
        ),
        # An instruction without a language: dropped, default target.
        ("ترجم الجملة التالية البحث عن فرص عمل في ألمانيا", None, "البحث عن فرص عمل في ألمانيا"),
        ("سأتأخر غدا ترجم هذا إلى الألمانية", "de", "سأتأخر غدا"),
        # Whisper's spelling of الإنجليزية in a real capture.
        ("أنا متعب اليوم، ترجم هذا إلى الاندليزية.", "en", "أنا متعب اليوم"),
        ("من فضلك ترجم إلى الإنجليزية من أين أنت", "en", "من أين أنت"),
        ("ترجم من العربية إلى الألمانية أنا جائع", "de", "أنا جائع"),
        ("ترجم لي هذا النص بالعربي إلى الإنجليزية أنا جائع", "en", "أنا جائع"),
        # Whisper got a letter of the instruction wrong (the user's captures):
        # "تلجم" for ترجم, "للغاة" for للغة, "العلمانية" for الألمانية.
        ("تلجم النص الآتي للغاة الألمانية أريد تحسين واجهة المستخدم", "de", "أريد تحسين واجهة المستخدم"),
        ("ترجم الاتي للغة العلمانية اريد تحسين اليو اي", "de", "اريد تحسين اليو اي"),
        ("تترجم هذا إلى الإنجليزية أنا جائع", "en", "أنا جائع"),
        ("أنا جائع، ترجم هذا إلى العلمانية", "de", "أنا جائع"),
        # English
        (
            'Translate the following sentence into German: "Search for job opportunities in Germany."',
            "de",
            "Search for job opportunities in Germany.",
        ),
        ("Translate from German to English: Ich habe Hunger.", "en", "Ich habe Hunger."),
        ("Translate into German, I speak English at work.", "de", "I speak English at work."),
        # German, instruction first or last, verb first or last.
        ("Übersetze das bitte ins Arabische: Ich komme morgen später.", "ar", "Ich komme morgen später."),
        ("Ich komme morgen später, übersetze das auf Arabisch.", "ar", "Ich komme morgen später"),
        ("ich komme morgen später übersetze das auf arabisch", "ar", "ich komme morgen später"),
        (
            "Ich komme morgen später. Kannst du das bitte auf Arabisch übersetzen?",
            "ar",
            "Ich komme morgen später.",
        ),
        ("Übersetze von Arabisch auf Deutsch أنا جائع", "de", "أنا جائع"),
        ("Auf Englisch: Ich habe morgen frei.", "en", "Ich habe morgen frei."),
        ("Ich liebe das, übersetze es auf Englisch.", "en", "Ich liebe das"),
    ],
)
def test_instruction_is_split_off(transcript, target, content):
    assert split_translation_instruction(transcript) == (target, content)


@pytest.mark.parametrize(
    "transcript",
    [
        # Languages that belong to the content.
        "Ich spreche gerne Arabisch und Deutsch.",
        "Kannst du mir sagen, wie man das auf Englisch sagt?",
        "أنا أتكلم بالعربي مع عائلتي",
        "I need a translator who speaks German.",
        # Close to an instruction, but ordinary sentences: ترجع ("you return")
        # is one letter from ترجم, العلمانية ("secularism") one from الألمانية.
        "ترجع إلى اللغة العربية بعد العطلة",
        "أنا مهتم بالعلمانية",
        "أدرس العلمانية في الجامعة",
        "هذا مهم للغاية الآن",
        # A misspelt verb without a language is not an instruction.
        "تلجم النص الآتي أريد تحسين واجهة المستخدم",
        # Nothing left to translate.
        "Translate this to Arabic",
        "ترجم إلى الألمانية",
        "",
    ],
)
def test_no_instruction(transcript):
    assert split_translation_instruction(transcript) == (None, transcript)


def test_language_in_content_after_an_instruction_is_not_the_target():
    # "translate the following sentence: I speak Arabic" — the name follows
    # content words, not "to / in / إلى".
    assert split_translation_instruction("ترجم الجملة الآتية أنا أتكلم بالعربي") == (
        None,
        "أنا أتكلم بالعربي",
    )


class _FakeBackend:
    model_size = "4B"

    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.reply


async def test_spoken_target_overrides_the_setting(monkeypatch):
    backend = _FakeBackend("Suche nach Jobangeboten in Deutschland.")
    monkeypatch.setattr(translation.llm_service, "get_llm_model", lambda: backend)

    text, _, used = await translation.translate_transcript(
        "ترجم الجملة الآتية إلى اللغة الألمانية البحث عن فرص عمل في ألمانيا", "en"
    )

    assert (text, used) == ("Suche nach Jobangeboten in Deutschland.", "de")
    assert backend.calls[0]["prompt"] == (
        "Translate this Arabic transcript into German:\nالبحث عن فرص عمل في ألمانيا"
    )


async def test_setting_is_used_without_a_spoken_target(monkeypatch):
    backend = _FakeBackend("I'm coming later tomorrow.")
    monkeypatch.setattr(translation.llm_service, "get_llm_model", lambda: backend)

    _, _, used = await translation.translate_transcript("Ich komme morgen später.", "en")

    assert used == "en"
    assert backend.calls[0]["prompt"].endswith("into English:\nIch komme morgen später.")
