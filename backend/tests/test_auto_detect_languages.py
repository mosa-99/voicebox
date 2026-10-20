"""Auto-detect among the languages the user speaks.

With ``capture_settings.language`` "auto", Whisper picks from ~99 languages
and turned one user's short Arabic and German dictations into Icelandic
("Tessgíl, tegirrað, rákað máginn." for "تسجيل تجربة رقمها").
``auto_detect_languages`` limits detection to the languages the user
speaks. The probabilities and trial scores below are the ones Whisper Turbo
produced for the user's own recordings.

Usage:
    python -m pytest backend/tests/test_auto_detect_languages.py -v
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend import config
from backend.backends.stt_language import (
    LanguageTrial,
    choose_language,
    compression_ratio,
    normalize_languages,
)
from backend.database import Base, get_db
from backend.database.migrations import _migrate_capture_settings

ALLOWED = ["de", "ar", "en"]


def _probs(**top):
    """Whisper-style distribution: the given languages plus a long tail."""
    probs = {code: 0.0001 for code in ("en", "de", "ar", "is", "no", "sv", "fr", "es", "ko")}
    probs.update(top)
    return probs


def _trials(scores):
    calls = []

    def trial(code):
        calls.append(code)
        return LanguageTrial(*scores[code])

    return trial, calls


# ── choose_language ──────────────────────────────────────────────────


def test_detected_language_is_kept_when_allowed():
    trial, calls = _trials({})
    assert choose_language(_probs(de=0.96, en=0.035), ALLOWED, trial) == "de"
    assert calls == []  # no extra decoding when Whisper is already right


def test_icelandic_guess_is_replaced_by_the_best_allowed_decode():
    # "تسجيل تجربة رقمها": Icelandic 0.95, English 0.03, Arabic 0.002.
    # Picking the likeliest allowed language would give English.
    probs = _probs(**{"is": 0.945, "en": 0.029, "de": 0.004, "ar": 0.002})
    trial, calls = _trials({"en": (-1.03, 0.7), "de": (-1.14, 0.8), "ar": (-0.37, 0.7)})
    assert choose_language(probs, ALLOWED, trial) == "ar"
    assert calls == ["en", "de", "ar"]  # likeliest first


def test_a_decode_stuck_in_a_loop_loses_despite_its_logprob():
    # German audio forced to Arabic repeated "لديوهماً" with a high logprob.
    probs = _probs(**{"is": 0.9, "de": 0.05})
    trial, _ = _trials({"de": (-0.38, 0.8), "ar": (-0.17, 17.5), "en": (-0.75, 0.8)})
    assert choose_language(probs, ALLOWED, trial) == "de"


def test_when_every_decode_loops_the_best_logprob_still_wins():
    probs = _probs(**{"is": 0.9})
    trial, _ = _trials({"de": (-0.9, 3.0), "ar": (-0.5, 4.0), "en": (-0.7, 5.0)})
    assert choose_language(probs, ALLOWED, trial) == "ar"


def test_codes_the_model_does_not_know_are_ignored():
    probs = _probs(**{"is": 0.9, "de": 0.05})
    trial, calls = _trials({"de": (-0.4, 0.8)})
    assert choose_language(probs, ["xx", "de"], trial) == "de"
    assert calls == ["de"]
    # Nothing usable left: fall back to Whisper's own guess.
    assert choose_language(probs, ["xx"], trial) == "is"


def test_normalize_languages():
    assert normalize_languages(None) == []
    assert normalize_languages(["DE", " ar ", "de", "", "auto", "en"]) == ["de", "ar", "en"]


def test_compression_ratio_flags_repetition():
    assert compression_ratio("") == 0.0
    assert compression_ratio("Ich gehe morgen zum Zahnarzt.") < 2.4
    assert compression_ratio("لديوهماً " * 40) > 2.4


# ── MLX backend ──────────────────────────────────────────────────────


@pytest.fixture
def mlx_backend():
    pytest.importorskip("torch")
    from backend.backends import mlx_backend

    return mlx_backend


def _fake_whisper():
    model = MagicMock()
    model.generate.return_value = SimpleNamespace(text=" Hallo ")
    return model


def _stt(mlx_backend, model):
    backend = mlx_backend.MLXSTTBackend("turbo")
    backend.model = model
    return backend


async def test_mlx_without_restriction_keeps_whisper_detection(mlx_backend):
    model = _fake_whisper()
    text = await _stt(mlx_backend, model).transcribe("a.wav", None, "turbo")
    assert text == "Hallo"
    model.generate.assert_called_once_with("a.wav")


async def test_mlx_explicit_language_wins_over_restriction(mlx_backend, monkeypatch):
    choose = MagicMock()
    monkeypatch.setattr(mlx_backend, "_choose_mlx_language", choose)
    model = _fake_whisper()
    await _stt(mlx_backend, model).transcribe("a.wav", "fr", "turbo", allowed_languages=ALLOWED)
    model.generate.assert_called_once_with("a.wav", language="fr")
    choose.assert_not_called()


async def test_mlx_single_allowed_language_is_forced(mlx_backend, monkeypatch):
    choose = MagicMock()
    monkeypatch.setattr(mlx_backend, "_choose_mlx_language", choose)
    model = _fake_whisper()
    await _stt(mlx_backend, model).transcribe("a.wav", None, "turbo", allowed_languages=["AR"])
    model.generate.assert_called_once_with("a.wav", language="ar")
    choose.assert_not_called()


async def test_mlx_restriction_transcribes_in_the_chosen_language(mlx_backend, monkeypatch, tmp_path):
    pytest.importorskip("mlx_audio.stt.utils")
    wav = tmp_path / "a.wav"
    sf.write(wav, np.zeros(16000, dtype=np.float32), 16000)
    choose = MagicMock(return_value="ar")
    monkeypatch.setattr(mlx_backend, "_choose_mlx_language", choose)
    model = _fake_whisper()

    await _stt(mlx_backend, model).transcribe(str(wav), None, "turbo", allowed_languages=ALLOWED)

    assert choose.call_args.args[2] == ALLOWED
    audio = model.generate.call_args.args[0]
    assert not isinstance(audio, str)  # the decoded audio is reused, not re-read
    assert model.generate.call_args.kwargs == {"language": "ar"}


def test_mlx_choice_encodes_once_and_decodes_each_candidate(mlx_backend):
    mx = pytest.importorskip("mlx.core")
    pytest.importorskip("mlx_audio.stt.models.whisper.decoding")
    scores = {"en": (-1.03, 0.7), "de": (-1.14, 0.8), "ar": (-0.37, 0.7)}
    model = MagicMock()
    model.dims.n_mels = 128
    model.dtype = mx.float16
    model.encoder.side_effect = lambda mel: mel
    model.detect_language.return_value = (None, _probs(**{"is": 0.945, "en": 0.029, "de": 0.004, "ar": 0.002}))
    model.decode.side_effect = lambda features, options: SimpleNamespace(
        avg_logprob=scores[options.language][0], compression_ratio=scores[options.language][1]
    )

    audio = mx.zeros(16000 * 3)
    assert mlx_backend._choose_mlx_language(model, audio, ALLOWED) == "ar"
    model.encoder.assert_called_once()
    assert model.decode.call_count == 3


def test_mlx_choice_falls_back_to_whisper_when_detection_breaks(mlx_backend):
    mx = pytest.importorskip("mlx.core")
    model = MagicMock()
    model.dims.n_mels = 128
    model.dtype = mx.float16
    model.encoder.side_effect = RuntimeError("mlx-audio changed")
    assert mlx_backend._choose_mlx_language(model, mx.zeros(16000), ALLOWED) is None


# ── settings + capture routes ────────────────────────────────────────


def test_migration_adds_an_empty_restriction():
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE capture_settings (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO capture_settings (id) VALUES (1)"))
        conn.commit()

    inspector = inspect(engine)
    _migrate_capture_settings(engine, inspector, set(inspector.get_table_names()))

    with engine.connect() as conn:
        value = conn.execute(text("SELECT auto_detect_languages FROM capture_settings")).scalar_one()
    assert json.loads(value) == []


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.routes.captures import router as captures_router
    from backend.routes.settings import router as settings_router
    from backend.services import captures as captures_service

    monkeypatch.setattr(config, "_data_dir", tmp_path)
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    whisper = MagicMock()
    whisper.model_size = "turbo"
    whisper.transcribe = AsyncMock(return_value="تجربة رقم واحد")
    monkeypatch.setattr(captures_service, "get_whisper_model", lambda: whisper)

    app = FastAPI()
    app.include_router(captures_router)
    app.include_router(settings_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.whisper = whisper
        yield test_client


def _wav_bytes(tmp_path):
    path = tmp_path / "upload.wav"
    sf.write(path, np.zeros(16000, dtype=np.float32), 16000)
    return path.read_bytes()


def test_settings_store_the_restriction(client):
    assert client.get("/settings/captures").json()["auto_detect_languages"] == []

    response = client.put("/settings/captures", json={"auto_detect_languages": ALLOWED})
    assert response.status_code == 200
    assert client.get("/settings/captures").json()["auto_detect_languages"] == ALLOWED

    assert client.put("/settings/captures", json={"auto_detect_languages": ["German"]}).status_code == 422


def test_capture_on_auto_detects_among_the_saved_languages(client, tmp_path):
    client.put("/settings/captures", json={"language": "auto", "auto_detect_languages": ALLOWED})

    response = client.post(
        "/captures",
        files={"file": ("a.wav", _wav_bytes(tmp_path), "audio/wav")},
        data={"source": "dictation"},
    )

    assert response.status_code == 200, response.text
    args = client.whisper.transcribe.call_args
    assert args.args[1] is None
    assert args.kwargs["allowed_languages"] == ALLOWED

    capture_id = response.json()["id"]
    client.whisper.transcribe.reset_mock()
    assert client.post(f"/captures/{capture_id}/retranscribe", json={}).status_code == 200
    args = client.whisper.transcribe.call_args
    assert args.args[1] is None
    assert args.kwargs["allowed_languages"] == ALLOWED


def test_capture_with_a_fixed_language_still_forces_it(client, tmp_path):
    client.put("/settings/captures", json={"language": "de", "auto_detect_languages": ALLOWED})

    response = client.post(
        "/captures",
        files={"file": ("a.wav", _wav_bytes(tmp_path), "audio/wav")},
        data={"source": "dictation"},
    )

    assert response.status_code == 200, response.text
    assert client.whisper.transcribe.call_args.args[1] == "de"
