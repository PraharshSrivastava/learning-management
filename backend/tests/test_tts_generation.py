def test_tts_uses_registered_sana_clone(tmp_path, monkeypatch):
    from pipelines import script_generator

    captured = {}

    class FakeResponse:
        status_code = 200
        content = b"RIFFfakeWAVE"
        text = ""

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(script_generator, "TTS_ENDPOINT", "https://tts.example")
    monkeypatch.setattr(script_generator, "TTS_VOICE", "sana")
    monkeypatch.setattr(script_generator, "TTS_TEMPERATURE", 0.6)
    monkeypatch.setattr(script_generator, "TTS_SPEED", 1.0)
    monkeypatch.setattr(script_generator.requests, "post", fake_post)

    output_path = tmp_path / "slide.wav"

    assert script_generator.synthesize_speech_for_slide("Hello.", str(output_path))
    assert captured["url"] == "https://tts.example/clone"
    assert captured["json"] == {"voice_name": "sana", "text": "Hello.", "language": "English", "temperature": 0.6, "top_p": 0.95, "top_k": 50}
    assert output_path.read_bytes() == b"RIFFfakeWAVE"


def test_tts_clone_route_trims_trailing_slash(tmp_path, monkeypatch):
    from pipelines import script_generator

    captured = {}

    class FakeResponse:
        status_code = 200
        content = b"RIFFfakeWAVE"
        text = ""

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(script_generator, "TTS_ENDPOINT", "https://tts.example/")
    monkeypatch.setattr(script_generator, "TTS_VOICE", "sana")
    monkeypatch.setattr(script_generator, "TTS_TEMPERATURE", 0.6)
    monkeypatch.setattr(script_generator, "TTS_SPEED", 1.0)
    monkeypatch.setattr(script_generator.requests, "post", fake_post)

    assert script_generator.synthesize_speech_for_slide("Hello.", str(tmp_path / "slide.wav"))
    assert captured["url"] == "https://tts.example/clone"
    assert captured["json"] == {
        "voice_name": "sana",
        "text": "Hello.",
        "language": "English",
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 50,
    }
