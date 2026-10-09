import pytest

from app.generation.captions import CaptionsUnavailable, display_words, group_cues, serialize_vtt


def test_readable_acronym_mapping_and_slide_offset():
    transcript, mapping = display_words("Upload to CRM.")
    assert transcript == "Upload to C R M."
    assert mapping[-1] == ("CRM.", 3)
    words = [
        {"text": word, "start": i * 0.5, "end": (i + 1) * 0.5}
        for i, word in enumerate(["Upload", "to", "C", "R", "M"])
    ]
    assert group_cues("Upload to CRM.", words, 3, 80) == [
        {"start": 80, "end": 82.5, "text": "Upload to CRM."}
    ]


def test_silence_is_not_included_in_cues():
    words = [{"text": "Save", "start": 0, "end": 1}, {"text": "Upload", "start": 2, "end": 3}]
    assert group_cues("Save. Upload.", words, 4) == [
        {"start": 0, "end": 1, "text": "Save."},
        {"start": 2, "end": 3, "text": "Upload."},
    ]


def test_financial_normalization_preserves_readable_text():
    transcript, mapping = display_words("Revenue in FY 25-26 was INR 1,000 and rose 5%.")
    assert "financial year 25 26" in transcript
    assert (
        " ".join(text for text, count in mapping)
        == "Revenue in FY 25-26 was INR 1,000 and rose 5%."
    )
    assert ("FY 25-26", 4) in mapping


@pytest.mark.parametrize(
    "words",
    [
        [{"text": "Save", "start": 0, "end": float("nan")}],
        [{"text": "Save", "start": 0, "end": 4}],
        [{"text": "Wrong", "start": 0, "end": 1}],
        [],
    ],
)
def test_invalid_or_incomplete_alignment_is_rejected(words):
    with pytest.raises(CaptionsUnavailable):
        group_cues("Save.", words, 3)


def test_vtt_escapes_markup_and_preserves_unicode():
    content = serialize_vtt([{"start": 80.001, "end": 82, "text": "₹100 & <safe>"}])
    assert "00:01:20.001 --> 00:01:22.000" in content
    assert "₹100 &amp; &lt;safe&gt;" in content


def test_overlapping_cues_are_rejected():
    with pytest.raises(CaptionsUnavailable):
        serialize_vtt(
            [{"start": 0, "end": 2, "text": "First"}, {"start": 1, "end": 3, "text": "Second"}]
        )


def test_module_assets_are_bound_to_video_and_idempotent(monkeypatch, tmp_path):
    import json
    import sys
    import types

    from app.generation import captions

    video = tmp_path / "module.mp4"
    audio = tmp_path / "slide.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    slides = [{"script": "Save.", "audio_path": str(audio)}]
    monkeypatch.setattr(captions, "resolve_public_asset_path", lambda value, config: audio)
    # Exercise the caption pipeline independently of DB/provider initialization.
    monkeypatch.setitem(
        sys.modules,
        "app.generation.video",
        types.SimpleNamespace(audio_duration=lambda name: 3 if name.endswith(".mp4") else 2),
    )
    calls = []

    def align(path, text):
        calls.append(text)
        return [{"text": "Save", "start": 0, "end": 1}]

    monkeypatch.setattr(captions, "align_slide", align)
    captions.record_narration_source(audio, "Save.")
    captions.record_video_source(video, slides, [3])
    assert captions.generate_module_captions(video, slides) == "generated"
    metadata = json.loads(video.with_suffix(".captions.json").read_text())
    assert metadata["video_sha256"] == captions.digest(video)
    assert metadata["vtt_sha256"] == captions.digest(video.with_suffix(".vtt"))
    assert captions.generate_module_captions(video, slides) == "skipped_valid_captions"
    assert calls == ["Save."]
    audio.write_bytes(b"changed narration")
    with pytest.raises(CaptionsUnavailable, match="mismatch"):
        captions.check_video_source(video, slides)
    with pytest.raises(CaptionsUnavailable, match="provenance"):
        captions.generate_module_captions(video, slides)
    assert not video.with_suffix(".media.lock").exists()


def test_alignment_command_is_validated_as_argv():
    from app.core.settings import Settings

    assert Settings(caption_align_command='["python", "worker.py"]').caption_align_command == (
        "python",
        "worker.py",
    )
    assert Settings(caption_align_command="[]").caption_align_command == ()
    for command in ['"python worker.py"', "[1]", '[""]']:
        with pytest.raises(ValueError):
            Settings(caption_align_command=command)


def test_narration_cache_cannot_reuse_audio_for_changed_script(tmp_path):
    from app.generation.captions import narration_matches, record_narration_source

    audio = tmp_path / "slide.wav"
    audio.write_bytes(b"audio")
    assert not narration_matches(audio, "Save.")
    record_narration_source(audio, "Save.")
    assert narration_matches(audio, "Save.")
    assert not narration_matches(audio, "Different narration.")
    audio.write_bytes(b"replaced audio")
    assert not narration_matches(audio, "Save.")


def test_module_lock_prevents_render_backfill_conflict(tmp_path):
    from app.generation.captions import module_lock

    video = tmp_path / "module.mp4"
    with module_lock(video):
        with pytest.raises(CaptionsUnavailable, match="already running"):
            with module_lock(video):
                pytest.fail("Concurrent work must not acquire the lock")
    assert not video.with_suffix(".media.lock").exists()
