"""The refinement guard: catches a refine model that translated or answered
the transcript instead of cleaning it up, and names the language it must
keep."""

import pytest

from backend.services.refinement import is_faithful_refinement, transcript_language


@pytest.mark.parametrize(
    ("transcript", "refined", "faithful"),
    [
        # German turned English (seen with Qwen3 4B).
        (
            "Das ist mein erster Test auf Deutsch. Die Datum ist 27. April 2017.",
            "This is my first test in German. The date is April 27, 2017.",
            False,
        ),
        (
            "Das ist mein erster Test auf Deutsch. Die Datum ist 27. April 2017.",
            "Das ist mein erster Test auf Deutsch. Das Datum ist 27. April 2017.",
            True,
        ),
        ("kannst du mir sagen wie spät es ist", "Can you tell me what time it is?", False),
        ("was ist in der datei an der stelle", "Was ist in der Datei an der Stelle?", True),
        # Arabic turned English.
        ("كيف يتم تحسين أداء جهازك", "How do you improve the performance of your device?", False),
        ("كيف يتم تحسين أداء جهازك", "كيف يتم تحسين أداء جهازك؟", True),
        # An answer instead of a cleanup.
        (
            "تهدث باللغة العربية إن أمكنك",
            "بالطبع، إليك بعض الجمل باللغة العربية:\n\n- كيف تبدأ؟\n- أنت متعب؟\n- هل أنت متأكد؟\n- متى تبدأ؟",
            False,
        ),
        ("so um the meeting is at three pm you know on tuesday", "So the meeting is at three pm on Tuesday.", True),
        ("ok", "OK.", True),
        ("URL URL", "", False),
    ],
)
def test_is_faithful_refinement(transcript, refined, faithful):
    assert is_faithful_refinement(transcript, refined) is faithful


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Das ist mein erster Test auf Deutsch.", "German"),
        ("ich muss noch den pull request auf github mergen und dann die app neu bauen", "German"),
        ("كيف يتم تحسين أداء جهازك", "Arabic"),
        ("so um the meeting is at three pm you know on tuesday", "English"),
        ("Tessgíl, tegirrað, rákað máginn.", None),
    ],
)
def test_transcript_language(text, language):
    assert transcript_language(text) == language
