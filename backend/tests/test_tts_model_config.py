"""Configurable TTS model regression tests."""

import pytest

from app.core.settings import Settings


def test_tts_model_configuration_and_validation():
    assert Settings().tts_model_name == "qwen3-tts"
    assert Settings(tts_model_name=" Qwen/Qwen3-TTS-12Hz-1.7B-Base ").tts_model_name == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    for name in ("", "   "):
        with pytest.raises(ValueError):
            Settings(tts_model_name=name)


def test_new_settings_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("TTS_MODEL_NAME", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    monkeypatch.setenv("APP_ENV", "development")
    configured = Settings.from_environment()
    assert configured.tts_model_name == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def test_tts_request_uses_configured_model_without_streaming(monkeypatch, tmp_path):
    from app.generation import tts

    captured = {}

    class Response:
        status_code = 200
        content = b"RIFF-test-audio"

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(tts, "TTS_MODEL_NAME", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    monkeypatch.setattr(tts.requests, "post", post)
    monkeypatch.setattr(tts, "_apply_tts_speed", lambda _: True)
    assert tts.synthesize_speech_for_slide("Hello", str(tmp_path / "audio.wav"))
    assert captured["json"]["model"] == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    assert captured["json"]["response_format"] == "wav"
    assert not captured["json"].get("stream", False)
