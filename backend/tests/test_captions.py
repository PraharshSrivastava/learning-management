from pathlib import Path

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


def test_zero_length_word_within_phrase_is_accepted():
    # Observed from Qwen3-ForcedAligner on real narration: "to" snapped to one frame boundary.
    words = [
        {"text": "questions", "start": 10.88, "end": 11.44},
        {"text": "to", "start": 11.44, "end": 11.44},
        {"text": "dig", "start": 11.44, "end": 11.84},
    ]
    assert group_cues("questions to dig.", words, 12) == [
        {"start": 10.88, "end": 11.84, "text": "questions to dig."}
    ]


def test_long_sentence_is_split_evenly_without_orphan_word():
    # Real module 1 narration that previously left "solutions." as its own 0.9 s cue.
    script = (
        "By the end, you will know how to truly hear your customers before offering any solutions."
    )
    words = [
        {"text": word, "start": i * 0.3, "end": (i + 1) * 0.3}
        for i, word in enumerate(display_words(script)[0].rstrip(".").split())
    ]
    cues = group_cues(script, words, 6)
    assert [cue["text"] for cue in cues] == [
        "By the end, you will know how to truly hear",
        "your customers before offering any solutions.",
    ]
    assert all(len(cue["text"]) <= 78 for cue in cues)


def test_long_phrase_prefers_comma_and_respects_duration():
    words = [{"text": f"w{i}", "start": i, "end": i + 0.9} for i in range(8)]
    cues = group_cues("w0 w1 w2, w3 w4 w5 w6 w7.", words, 9)
    assert [cue["text"] for cue in cues] == ["w0 w1 w2,", "w3 w4 w5 w6 w7."]
    assert all(cue["end"] - cue["start"] <= 6 for cue in cues)


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

    def align(items):
        calls.extend(text for _, text in items)
        return [[{"text": "Save", "start": 0, "end": 1}] for _ in items]

    monkeypatch.setattr(captions, "align_slides", align)
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


def _tone(path, seconds, rate=16000):
    import array
    import math
    import wave

    samples = array.array(
        "h",
        (int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(int(seconds * rate))),
    )
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.tobytes())


def _legacy_module(tmp_path, monkeypatch, narration=(1.0, 1.5), pause=1.0):
    """A pre-provenance video: each slide's narration followed by a silent pause."""
    import subprocess

    import imageio_ffmpeg

    from app.generation import captions

    monkeypatch.setattr(captions, "resolve_public_asset_path", lambda value, config: Path(value))
    slides, inputs = [], []
    for index, seconds in enumerate(narration, start=1):
        audio = tmp_path / f"slide_{index}.wav"
        _tone(audio, seconds)
        slides.append({"script": f"Slide {index} speaks.", "audio_path": str(audio)})
        inputs += ["-i", str(audio)]
    count = len(narration)
    graph = "".join(f"[{i}:a]apad=pad_dur={pause}[a{i}];" for i in range(count))
    graph += "".join(f"[a{i}]" for i in range(count)) + f"concat=n={count}:v=0:a=1"
    video = tmp_path / "module_1.mp4"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", *inputs,
         "-filter_complex", graph, "-c:a", "aac", str(video)],
        check=True,
    )
    return video, slides


def _fake_alignment(monkeypatch, calls=None):
    from app.generation import captions

    def align(items):
        if calls is not None:
            calls.append(len(items))
        return [
            [
                {"text": "Slide", "start": 0.1, "end": 0.3},
                {"text": text.split()[1], "start": 0.3, "end": 0.5},
                {"text": "speaks", "start": 0.5, "end": 0.9},
            ]
            for _, text in items
        ]

    monkeypatch.setattr(captions, "align_slides", align)


def test_legacy_video_is_captioned_from_its_own_soundtrack(monkeypatch, tmp_path):
    import json

    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    calls = []
    _fake_alignment(monkeypatch, calls)
    assert captions.generate_legacy_module_captions(video, slides) == "generated"
    assert calls == [2], "all slides of a module go to one aligner run"
    content = video.with_suffix(".vtt").read_text(encoding="utf-8")
    assert "00:00:00.100 --> 00:00:00.900\nSlide 1 speaks." in content
    # Slide 2 starts after slide 1's narration (1.0 s) and its pause (about 1.0 s).
    assert "\n00:00:02.1" in content
    metadata = json.loads(video.with_suffix(".captions.json").read_text())
    assert metadata["method"] == captions.LEGACY_METHOD
    assert abs(metadata["pause_seconds"] - 1.0) < 0.1
    assert metadata["cue_count"] == 2
    assert metadata["vtt_sha256"] == metadata["fingerprint"]
    assert metadata["fingerprint"] == captions.digest(video.with_suffix(".vtt"))
    assert metadata["video_size"] == video.stat().st_size
    assert captions.generate_legacy_module_captions(video, slides) == "skipped_valid_captions"
    assert calls == [2]
    assert not video.with_suffix(".media.lock").exists()


def test_legacy_narration_that_does_not_add_up_is_refused(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    _tone(Path(slides[1]["audio_path"]), 6)  # Narration replaced after the video was made.
    _fake_alignment(monkeypatch)
    with pytest.raises(CaptionsUnavailable, match="does not add up"):
        captions.generate_legacy_module_captions(video, slides)
    assert not video.with_suffix(".vtt").exists()
    assert not video.with_suffix(".captions.json").exists()


def test_legacy_boundary_inside_speech_is_refused(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch, narration=(1.0, 2.0))
    # Same total length, but swapped slides no longer match the soundtrack pattern.
    first, second = slides[0]["audio_path"], slides[1]["audio_path"]
    slides[0]["audio_path"], slides[1]["audio_path"] = second, first
    _fake_alignment(monkeypatch)
    with pytest.raises(CaptionsUnavailable, match="Slide 1 narration does not match"):
        captions.generate_legacy_module_captions(video, slides)
    assert not video.with_suffix(".vtt").exists()


def test_legacy_alignment_that_collapses_is_refused(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    monkeypatch.setattr(
        captions,
        "align_slides",
        lambda items: [
            [{"text": word.strip("."), "start": 0.4, "end": 0.4} for word in text.split()]
            for _, text in items
        ],
    )
    with pytest.raises(CaptionsUnavailable, match="does not match the spoken audio"):
        captions.generate_legacy_module_captions(video, slides)


def test_backfill_skips_generator_videos_and_reports_each_module(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    _fake_alignment(monkeypatch)
    module = {"module_number": 1, "video_path": str(video), "slides": slides}
    dry = captions.backfill_module_captions(module, apply=False)
    assert dry["status"] == "dry_run" and dry["method"] == captions.LEGACY_METHOD
    assert abs(dry["pause_seconds"] - 1.0) < 0.1
    assert not video.with_suffix(".vtt").exists()
    assert captions.backfill_module_captions(module, apply=True)["status"] == "generated"
    again = captions.backfill_module_captions(module, apply=True)
    assert again["status"] == "skipped_valid_captions"
    generator = {**module, "video_service": {"run_id": "run-1"}}
    skipped = captions.backfill_module_captions(generator, apply=True)
    assert skipped["status"] == "skipped_video_generator"
    video.with_suffix(".srt").write_text("1\n", encoding="utf-8")
    skipped = captions.backfill_module_captions(module, apply=True)
    assert skipped["status"] == "skipped_video_generator"
    missing = {"module_number": 2, "video_path": "", "slides": slides}
    assert captions.backfill_module_captions(missing, apply=True)["status"] == "skipped_no_video"
    video.with_suffix(".srt").unlink()
    _tone(Path(slides[1]["audio_path"]), 6)
    failed = captions.backfill_module_captions(module, apply=False)
    assert failed["status"] == "unavailable" and "does not add up" in failed["reason"]


def test_aligner_worker_loads_the_model_once_per_module(monkeypatch, tmp_path):
    import importlib.util
    import json
    import sys
    import types

    loads = []

    class Item:
        def __init__(self, text):
            self.text, self.start_time, self.end_time = text, 0.0, 0.5

    class Aligner:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            loads.append(args)
            return cls()

        def align(self, audio, text, language):
            return [[Item(word) for word in text.split()]]

    monkeypatch.setitem(sys.modules, "qwen_asr", types.SimpleNamespace(Qwen3ForcedAligner=Aligner))
    monkeypatch.setenv("CAPTION_ALIGN_MODEL_PATH", str(tmp_path))
    monkeypatch.delenv("CAPTION_ALIGN_THREADS", raising=False)
    path = Path(__file__).resolve().parents[1] / "scripts" / "align_captions_qwen.py"
    spec = importlib.util.spec_from_file_location("align_worker", path)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    request, result = tmp_path / "request.json", tmp_path / "result.json"
    items = [{"audio": "a.wav", "text": "one two"}, {"audio": "b.wav", "text": "three"}]
    request.write_text(json.dumps({"items": items, "language": "English"}))
    monkeypatch.setattr(sys, "argv", ["worker", str(request), str(result)])
    worker.main()
    assert len(loads) == 1
    results = json.loads(result.read_text())["results"]
    assert [[word["text"] for word in entry["words"]] for entry in results] == [
        ["one", "two"],
        ["three"],
    ]
    # The single-slide request format keeps working for existing callers.
    request.write_text(json.dumps({"audio": "a.wav", "text": "solo", "language": "English"}))
    worker.main()
    assert json.loads(result.read_text())["words"][0]["text"] == "solo"


def test_align_slides_round_trips_a_module_request_through_the_worker(monkeypatch, tmp_path):
    import sys

    from app.generation import captions

    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json, sys, pathlib\n"
        "request = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({'results': [\n"
        "    {'words': [{'text': item['text'], 'start': 0, 'end': 1}]} for item in request['items']]}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(captions.settings, "caption_align_command", (sys.executable, str(worker)))
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"")
    words = captions.align_slides([(audio, "one"), (audio, "two")])
    assert [entry[0]["text"] for entry in words] == ["one", "two"]
    assert captions.align_slide(audio, "solo")[0]["text"] == "solo"
