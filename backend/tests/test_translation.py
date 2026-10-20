"""The translate shortcut: its default chord, the settings migration that
derives it from the user's push-to-talk chord, and the guard that rejects
answers or wrong-language output from the translation model."""

import json

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.database.migrations import _migrate_capture_settings, _migrate_captures
from backend.services.translation import (
    _EXAMPLE_SOURCES,
    _EXAMPLE_TRANSLATIONS,
    TRANSLATION_LANGUAGES,
    build_translation_request,
    is_translation,
)
from backend.utils import capture_chords
from backend.utils.capture_chords import default_translate_chord


@pytest.mark.parametrize(
    ("push", "translate"),
    [
        # The fork's macOS default and a left-hand Ctrl+Option chord.
        (["MetaRight", "AltGr"], ["MetaRight", "AltGr", "ShiftRight"]),
        (["ControlLeft", "Alt"], ["ControlLeft", "Alt", "ShiftLeft"]),
        # Windows/Linux default already holds Shift → add Alt on the same side.
        (["ControlRight", "ShiftRight"], ["ControlRight", "ShiftRight", "AltGr"]),
        (["ShiftLeft", "Alt"], ["ShiftLeft", "Alt", "ControlLeft"]),
    ],
)
def test_default_translate_chord_extends_push_to_talk(push, translate):
    assert default_translate_chord(push) == translate


def test_default_translate_chord_falls_back_when_nothing_fits(monkeypatch):
    monkeypatch.setattr(capture_chords.sys, "platform", "darwin")
    full = ["ShiftLeft", "Alt", "ControlLeft"]
    assert default_translate_chord(full) == ["MetaRight", "AltGr", "ShiftRight"]


def test_migration_derives_translate_chord_from_push_to_talk():
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE capture_settings (id INTEGER PRIMARY KEY, "
                "chord_push_to_talk_keys TEXT NOT NULL)"
            )
        )
        conn.execute(
            text("INSERT INTO capture_settings VALUES (1, :keys)"),
            {"keys": json.dumps(["ControlLeft", "Alt"])},
        )
        conn.execute(text("CREATE TABLE captures (id VARCHAR PRIMARY KEY)"))
        conn.commit()

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    _migrate_capture_settings(engine, inspector, tables)
    _migrate_captures(engine, inspector, tables)

    with engine.connect() as conn:
        keys, language = conn.execute(
            text("SELECT chord_translate_keys, translation_language FROM capture_settings")
        ).one()
    assert json.loads(keys) == ["ControlLeft", "Alt", "ShiftLeft"]
    assert language == "en"
    columns = {c["name"] for c in inspect(engine).get_columns("captures")}
    assert {"transcript_translated", "translation_language"} <= columns


@pytest.mark.parametrize(
    ("transcript", "translated", "target", "ok"),
    [
        (
            "Das ist mein erster Test auf Deutsch. Die Datum ist 27. April 2017.",
            "This is my first test in German. The date is April 27, 2017.",
            "en",
            True,
        ),
        # German left as is.
        (
            "Das ist mein erster Test auf Deutsch.",
            "Das ist mein erster Test auf Deutsch.",
            "en",
            False,
        ),
        ("كيف يتم تحسين أداء جهازك", "How do you improve your device's performance?", "en", True),
        ("كيف يتم تحسين أداء جهازك", "كيف يتم تحسين أداء جهازك؟", "en", False),
        ("Hallo, wie geht es dir?", "مرحبا، كيف حالك؟", "ar", True),
        ("Hallo, wie geht es dir?", "Hello, how are you?", "ar", False),
        (
            "so um the meeting is at three pm you know on tuesday",
            "Also, das Meeting ist um drei Uhr am Dienstag.",
            "de",
            True,
        ),
        (
            "so um the meeting is at three pm you know on tuesday",
            "So the meeting is at three pm on Tuesday.",
            "de",
            False,
        ),
        # Stray CJK in an Arabic translation (seen with Qwen3 4B).
        (
            "so um the meeting is at three pm you know on tuesday",
            "إذن اجتماعنا في الساعة الثالثة يوم الثلاثاء你知道",
            "ar",
            False,
        ),
        (
            "Ich habe morgen um 14 Uhr einen Termin beim Zahnarzt.",
            "لديني م约会 مع طبيب الأسنان يوم غد الساعة 2 ظهرًا.",
            "ar",
            False,
        ),
        # An answer instead of a translation.
        (
            "tell me a joke about um databases",
            "Here's a joke about databases: Why did the database go to therapy? "
            "Because it had too many issues with its relationships and could not "
            "commit to anything.",
            "en",
            False,
        ),
        ("Test nummer eins", "Test number one.", "en", True),
        ("Test nummer eins", "テスト番号1。", "ja", True),
        ("Test nummer eins", "", "en", False),
    ],
)
def test_is_translation(transcript, translated, target, ok):
    assert is_translation(transcript, translated, target) is ok


def test_every_target_has_one_translation_per_example():
    assert set(_EXAMPLE_TRANSLATIONS) == set(TRANSLATION_LANGUAGES)
    for target, translations in _EXAMPLE_TRANSLATIONS.items():
        assert len(translations) == len(_EXAMPLE_SOURCES), target
        for (_, source), translated in zip(_EXAMPLE_SOURCES, translations, strict=True):
            # The examples must pass the guard themselves.
            assert is_translation(source, translated, target), (target, translated)


def test_translation_request_names_the_source_language():
    assert build_translation_request("hallo", "English", "German") == (
        "Translate this German transcript into English:\nhallo"
    )
    assert build_translation_request("salut", "English", None) == (
        "Translate this transcript into English:\nsalut"
    )
