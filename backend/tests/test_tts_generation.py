def test_cloned_voice_uses_clone_route_and_voice_name(tmp_path, monkeypatch):
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
    monkeypatch.setattr(script_generator, "TTS_VOICE", "ref_tejas")
    monkeypatch.setattr(script_generator, "TTS_SPEED", 1.0)
    monkeypatch.setattr(script_generator.requests, "post", fake_post)

    output_path = tmp_path / "slide.wav"

    assert script_generator.synthesize_speech_for_slide("Hello.", str(output_path))
    assert captured["url"] == "https://tts.example/clone"
    assert captured["json"] == {"text": "Hello.", "voice_name": "ref_tejas"}
    assert output_path.read_bytes() == b"RIFFfakeWAVE"


def test_default_speaker_uses_tts_route(tmp_path, monkeypatch):
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

    monkeypatch.setattr(script_generator, "TTS_ENDPOINT", "https://tts.example")
    monkeypatch.setattr(script_generator, "TTS_VOICE", "ryan")
    monkeypatch.setattr(script_generator, "TTS_SPEED", 1.0)
    monkeypatch.setattr(script_generator.requests, "post", fake_post)

    assert script_generator.synthesize_speech_for_slide("Hello.", str(tmp_path / "slide.wav"))
    assert captured["url"] == "https://tts.example/tts"
    assert captured["json"] == {
        "text": "Hello.",
        "language": "English",
        "speaker": "ryan",
    }
