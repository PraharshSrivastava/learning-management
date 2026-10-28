import subprocess
from pathlib import Path

import pytest

from app.generation.captions import CaptionsUnavailable, display_words, group_cues, serialize_vtt


@pytest.fixture(autouse=True)
def _default_caption_timing(monkeypatch):
    """Start every test at the shipped default: auto timing, no aligner configured."""
    from app.core.settings import settings

    monkeypatch.setattr(settings, "caption_timing", "auto")
    monkeypatch.setattr(settings, "caption_align_command", ())


def _use_aligner(monkeypatch):
    from app.core.settings import settings

    monkeypatch.setattr(settings, "caption_align_command", ("aligner",))


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
    _use_aligner(monkeypatch)
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
    _use_aligner(monkeypatch)


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
    _use_aligner(monkeypatch)
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


def test_narration_cache_rejects_audio_made_with_other_pace(tmp_path, monkeypatch):
    from app.core.settings import settings
    from app.generation.captions import narration_matches, record_narration_source

    audio = tmp_path / "slide.wav"
    audio.write_bytes(b"audio")
    record_narration_source(audio, "Save.")
    monkeypatch.setattr(settings, "tts_max_words_per_minute", 120)
    assert not narration_matches(audio, "Save.")


def test_captions_show_aml_and_fiu_ind_as_written():
    from app.generation.captions import display_words

    _, mapping = display_words("AML reports go to FIU-IND.")
    assert [word for word, _ in mapping] == ["AML", "reports", "go", "to", "FIU-IND."]


# Narration timing: captions timed from the measured narration, with no aligner.


def _speech(path, parts, rate=16000):
    """A WAV of ("tone" | "quiet", seconds) parts, so speech and pause times are exact."""
    import array
    import math
    import wave

    samples = array.array("h")
    for kind, seconds in parts:
        count = round(seconds * rate)
        if kind == "tone":
            samples.extend(int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(count))
        else:
            samples.extend([0] * count)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.tobytes())


def _layout(path, tmp_path, duration):
    from app.generation import captions

    return captions._speech_layout(captions._to_pcm(path, tmp_path / "pcm.wav"), duration)


def _vtt_cues(content):
    import re

    return [
        (_seconds(start), _seconds(end), text)
        for start, end, text in re.findall(r"(\S+) --> (\S+)\n(.+)\n", content)
    ]


def _seconds(stamp):
    hours, minutes, seconds = stamp.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _check_cue_rules(cues, start, end):
    """Minimum length, order, no overlap, and every cue inside the speech span."""
    assert cues and serialize_vtt(cues)
    for cue, following in zip(cues, cues[1:]):
        assert cue["end"] <= following["start"]
    assert all(cue["end"] - cue["start"] >= 0.8 - 1e-9 for cue in cues)
    assert cues[0]["start"] >= start and cues[-1]["end"] == round(end, 3)


def test_caption_timing_setting_is_validated_and_read_from_environment(monkeypatch):
    from app.core.settings import Settings

    assert Settings().caption_timing == "auto"
    assert Settings(caption_timing=" Narration ").caption_timing == "narration"
    with pytest.raises(ValueError):
        Settings(caption_timing="estimated")
    monkeypatch.setenv("CAPTION_TIMING", "off")
    assert Settings.from_environment().caption_timing == "off"


def test_auto_timing_uses_the_aligner_only_when_configured(monkeypatch):
    from app.generation import captions

    assert captions.caption_timing() == "narration"
    _use_aligner(monkeypatch)
    assert captions.caption_timing() == "aligned"
    for value in ("narration", "aligned", "off"):
        monkeypatch.setattr(captions.settings, "caption_timing", value)
        assert captions.caption_timing() == value


def test_edge_silence_is_trimmed_without_cutting_speech(tmp_path):
    from app.generation.captions import narration_cues

    audio = tmp_path / "slide.wav"
    _speech(audio, [("quiet", 0.3), ("tone", 2.0), ("quiet", 0.4)])
    start, end, pauses = _layout(audio, tmp_path, 2.7)
    # Speech is 0.3-2.3 s; a 50 ms margin shows the phrase just before the first sound.
    assert start == pytest.approx(0.25, abs=0.011)
    assert end == pytest.approx(2.35, abs=0.011)
    assert pauses == []
    cues = narration_cues("Report it today.", start, end, pauses)
    assert cues[0]["start"] == pytest.approx(0.25, abs=0.011)
    assert cues[-1]["end"] == pytest.approx(2.35, abs=0.011)


def test_silent_or_unreadable_narration_falls_back_to_the_whole_span(tmp_path):
    import array

    from app.generation.captions import _speech_layout

    audio = tmp_path / "silent.wav"
    _speech(audio, [("quiet", 1.0)])
    assert _layout(audio, tmp_path, 1.0) == (0.0, 1.0, [])
    assert _speech_layout(array.array("h"), 2.0) == (0.0, 2.0, [])


def test_narration_cues_follow_phrasing_rules_and_show_terms_as_written():
    import textwrap

    from app.generation.captions import WEAK_ENDINGS, narration_cues

    script = (
        "<b>AML</b> checks protect the firm. "
        "The principal officer of the reporting entity is responsible for filing reports "
        "with the FIU-IND on time, and for keeping records of the AML checks. "
        "Customers who want to open an account at the branch must provide the original "
        "documents for verification of the address and the identity. Ask why!"
    )
    cues = narration_cues(script, 0.2, 30.0)
    texts = [cue["text"] for cue in cues]
    assert texts[0] == "AML checks protect the firm."
    assert "FIU-IND" in " ".join(texts) and "eff eye you" not in " ".join(texts)
    for text in texts:
        assert len(text) <= 78
        assert len(textwrap.wrap(text, 42)) <= 2
        assert text.split()[-1].lower() not in WEAK_ENDINGS
        # A sentence end only ever closes a cue.
        assert all(not word.endswith((".", "!", "?")) for word in text.split()[:-1])
    assert texts[-1] == "Ask why!"
    assert all(len(text.split()) > 1 for text in texts)
    _check_cue_rules(cues, 0.2, 30.0)


def test_narration_split_never_ends_a_cue_on_a_weak_word():
    from app.generation.captions import _balanced_pieces, _spoken_words

    words = _spoken_words(
        "Customers who want to open an account at the branch must provide the original "
        "documents for verification of the address and the identity."
    )
    timed = [{**word, "start": i * 0.1, "end": i * 0.1 + 0.1} for i, word in enumerate(words)]
    # Splitting purely by balance would leave "the" dangling at the end of the first cue.
    assert _balanced_pieces(timed)[0][-1]["text"] == "the"
    pieces = _balanced_pieces(words, timed=False)
    assert [" ".join(word["text"] for word in piece) for piece in pieces] == [
        "Customers who want to open an account at the branch must provide",
        "the original documents for verification of the address and the identity.",
    ]


def test_acronyms_get_time_for_how_they_are_spoken(monkeypatch):
    from app.generation import captions

    script = "AML KYC NSE. We sat down."
    first, second = script.split(". ")
    assert len(first + ".") == len(second)
    cues = captions.narration_cues(script, 0.0, 6.0)
    assert cues[0]["end"] - cues[0]["start"] > 1.3 * (cues[1]["end"] - cues[1]["start"])

    # When the spoken mapping fails, written length is used instead.
    def unmappable(script):
        raise CaptionsUnavailable("Narration contains unalignable tokens")

    monkeypatch.setattr(captions, "display_words", unmappable)
    cues = captions.narration_cues(script, 0.0, 6.0)
    assert cues[0]["end"] == pytest.approx(3.0, abs=0.01)


def test_short_phrases_still_get_the_minimum_cue_time():
    from app.generation.captions import narration_cues

    script = (
        "Yes. The principal officer of the reporting entity is responsible for filing reports "
        "with the FIU-IND on time, and for keeping records of the AML checks. Done."
    )
    cues = narration_cues(script, 0.3, 12.0, offset=40.0)
    assert [cue["text"] for cue in cues][::3] == ["Yes.", "Done."]
    _check_cue_rules(cues, 40.3, 52.0)
    # Too little time for every phrase: equal shares, still ordered and inside the span.
    cramped = narration_cues(script, 0.0, 2.0)
    assert cramped[-1]["end"] == 2.0 and serialize_vtt(cramped)


def test_sentence_ends_are_pinned_to_audible_pauses(tmp_path):
    from app.generation.captions import narration_cues

    audio = tmp_path / "slide.wav"
    _speech(audio, [("tone", 2.0), ("quiet", 0.5), ("tone", 1.0), ("quiet", 0.5), ("tone", 2.0)])
    start, end, pauses = _layout(audio, tmp_path, 6.0)
    assert (start, end) == (0.0, 6.0)
    assert pauses == [pytest.approx((2.05, 2.45)), pytest.approx((3.55, 3.95))]
    script = "Check the customer. Then verify it. Report anything odd."
    cues = narration_cues(script, start, end, pauses)
    assert [(cue["start"], cue["end"]) for cue in cues] == [
        pytest.approx((0.0, 2.05)),
        pytest.approx((2.45, 3.55)),
        pytest.approx((3.95, 6.0)),
    ]
    # Without the pauses the middle sentence is only estimated, starting well before 2.45 s.
    assert narration_cues(script, start, end)[1]["start"] < 2.3


def test_pauses_far_from_any_sentence_end_are_ignored(tmp_path):
    from app.generation.captions import narration_cues

    audio = tmp_path / "slide.wav"
    _speech(audio, [("tone", 5.0), ("quiet", 0.5), ("tone", 0.5)])
    start, end, pauses = _layout(audio, tmp_path, 6.0)
    assert len(pauses) == 1
    # The first sentence is estimated to end at 3.36 s; the pause at 5.25 s is too far away.
    script = "Read the rule. Then apply."
    cues = narration_cues(script, start, end, pauses)
    assert cues == narration_cues(script, start, end)
    assert cues[0]["end"] == pytest.approx(3.36, abs=0.01)


def test_pause_matching_is_ordered_and_one_to_one():
    import random

    from app.generation.captions import _match_pauses

    # 100 units of spoken length over 10 s of speech, plus the pauses: 0.1 s per unit.
    both = [(2.0, 2.4), (6.4, 6.8)]
    assert _match_pauses([20, 60], [4, 4], both, 0.0, 10.8, 100) == {0: both[0], 1: both[1]}
    # A comma keeps its own pause; the sentence end after it has none.
    assert _match_pauses([20, 60], [1, 4], [(2.0, 2.4)], 0.0, 10.4, 100) == {0: (2.0, 2.4)}
    # A pause that only fits the later phrase end is not taken by the earlier one.
    assert _match_pauses([20, 60], [4, 4], [(6.0, 6.4)], 0.0, 10.4, 100) == {1: (6.0, 6.4)}
    # Two phrase ends near one pause: only one of them gets it.
    assert len(_match_pauses([20, 21], [4, 4], [(2.0, 2.4)], 0.0, 10.4, 100)) == 1
    # Too far (more than 1.5 s) from where the phrase should end.
    assert _match_pauses([50], [4], [(8.0, 8.3)], 0.0, 10.3, 100) == {}
    assert _match_pauses([], [], [(1.0, 1.2)], 0.0, 5.0, 50) == {}
    assert _match_pauses([20], [4], [], 0.0, 5.0, 50) == {}
    generator = random.Random(7)
    for _ in range(300):
        positions = sorted(generator.sample(range(1, 100), generator.randint(1, 8)))
        times = sorted(generator.uniform(0.3, 9.5) for _ in range(generator.randint(0, 8)))
        pauses = [
            (first + 0.02, first + 0.27)
            for first, second in zip(times, [*times[1:], 10.0])
            if second - first > 0.4
        ]
        anchors = _match_pauses(positions, [1.0] * len(positions), pauses, 0.0, 10.0, 100)
        used = [anchors[key] for key in sorted(anchors)]
        assert used == sorted(set(used)), "never reordered, never shared"


def test_pause_matching_stays_fast_and_accurate_on_a_long_slide():
    import time

    from app.generation.captions import _match_pauses

    # Ten minutes of narration: 300 phrase ends 2 s apart, each followed by its own pause.
    positions = [20.0 * (index + 1) for index in range(300)]
    pauses = [
        (2.0 * (index + 1) + 0.3 * index, 2.0 * (index + 1) + 0.3 * (index + 1))
        for index in range(300)
    ]
    end = pauses[-1][1] + 2.0
    began = time.perf_counter()
    anchors = _match_pauses(positions, [4.0] * 300, pauses, 0.0, end, 6020.0)
    assert time.perf_counter() - began < 10
    assert anchors == dict(enumerate(pauses))


def _rendered_module(tmp_path, monkeypatch, slides_spec, pause=1.0):
    """Render a module the way the LMS does: slide WAV plus transition pause, clips joined."""
    import subprocess

    import imageio_ffmpeg

    from app.generation import captions
    from app.generation import video as rendering

    monkeypatch.setattr(captions, "resolve_public_asset_path", lambda value, config: Path(value))
    frame = tmp_path / "frame.png"
    blank = ["-f", "lavfi", "-i", "color=c=white:s=64x64", "-frames:v", "1"]
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", *blank, str(frame)], check=True)
    slides, clips, durations = [], [], []
    for index, (parts, script) in enumerate(slides_spec):
        audio = tmp_path / f"slide_{index}.wav"
        _speech(audio, parts)
        captions.record_narration_source(audio, script)
        clip = tmp_path / f"clip_{index}.mp4"
        rendering.encode_slide_clip(
            str(frame), str(audio), str(clip), transition_pause_seconds=pause
        )
        clips.append(str(clip))
        durations.append(rendering.audio_duration(str(clip)))
        slides.append({"script": script, "audio_path": str(audio)})
    output = tmp_path / "module_1.mp4"
    rendering.concatenate_clips(clips, str(output), working_dir=str(tmp_path))
    captions.record_video_source(output, slides, durations)
    return output, slides, durations


def _aligner_from_transcript(monkeypatch, calls=None):
    """A stand-in aligner that times every expected token 0.1 s apart."""
    from app.generation import captions

    def align(items):
        if calls is not None:
            calls.append(len(items))
        return [
            [
                {"text": token, "start": i * 0.1, "end": i * 0.1 + 0.1}
                for i, token in enumerate(captions._tokens(text))
            ]
            for _, text in items
        ]

    monkeypatch.setattr(captions, "align_slides", align)
    _use_aligner(monkeypatch)


def test_rendered_module_gets_narration_timed_captions_without_an_aligner(monkeypatch, tmp_path):
    import json

    from app.generation import captions
    from app.generation.video import audio_duration

    video, slides, durations = _rendered_module(
        tmp_path,
        monkeypatch,
        [
            (
                [("quiet", 0.3), ("tone", 1.5), ("quiet", 0.4), ("tone", 1.0), ("quiet", 0.2)],
                "Customers open accounts. They bring documents.",
            ),
            ([("tone", 2.0)], "AML alerts go to FIU-IND."),
        ],
    )

    def no_aligner(items):
        raise AssertionError("no aligner is configured")

    monkeypatch.setattr(captions, "align_slides", no_aligner)
    assert captions.generate_module_captions(video, slides) == "generated"
    cues = _vtt_cues(video.with_suffix(".vtt").read_text(encoding="utf-8"))
    assert [text for _, _, text in cues] == [
        "Customers open accounts.",
        "They bring documents.",
        "AML alerts go to FIU-IND.",
    ]
    # Slide 1: edges trimmed, the second sentence pinned to the 1.8-2.2 s pause.
    assert cues[0][:2] == pytest.approx((0.25, 1.85), abs=0.011)
    assert cues[1][:2] == pytest.approx((2.15, 3.25), abs=0.011)
    # Slide 2 starts after slide 1's measured clip; its transition pause has no cue.
    assert cues[2][:2] == pytest.approx((durations[0], durations[0] + 2.0), abs=0.002)
    assert not any(start < durations[0] < end for start, end, _ in cues)
    metadata = json.loads(video.with_suffix(".captions.json").read_text(encoding="utf-8"))
    assert metadata["method"] == "narration-timing"
    assert metadata["fingerprint"] == metadata["vtt_sha256"]
    assert metadata["vtt_sha256"] == captions.digest(video.with_suffix(".vtt"))
    assert metadata["video_sha256"] == captions.digest(video)
    assert metadata["cue_count"] == 3
    assert metadata["duration"] == audio_duration(str(video))
    assert cues[-1][1] <= metadata["duration"]
    assert metadata["video_size"] == video.stat().st_size
    assert metadata["video_mtime"] == int(video.stat().st_mtime)
    assert metadata["inputs"] == captions.source_inputs(slides)
    assert captions.generate_module_captions(video, slides) == "skipped_valid_captions"
    assert not video.with_suffix(".media.lock").exists()

    # Once an aligner is configured, estimated captions are upgraded, then kept.
    calls = []
    _aligner_from_transcript(monkeypatch, calls)
    assert captions.generate_module_captions(video, slides) == "generated"
    metadata = json.loads(video.with_suffix(".captions.json").read_text(encoding="utf-8"))
    assert metadata["method"] == "forced-alignment" and calls == [2]
    assert captions.generate_module_captions(video, slides) == "skipped_valid_captions"
    # Narration timing never replaces aligned captions.
    monkeypatch.setattr(captions.settings, "caption_timing", "narration")
    assert captions.generate_module_captions(video, slides) == "skipped_valid_captions"
    assert calls == [2]


def test_rendered_module_provenance_is_still_enforced(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides, _ = _rendered_module(
        tmp_path, monkeypatch, [([("tone", 1.0)], "Save the file.")]
    )
    _speech(Path(slides[0]["audio_path"]), [("tone", 1.2)])
    with pytest.raises(CaptionsUnavailable, match="provenance"):
        captions.generate_module_captions(video, slides)
    assert not video.with_suffix(".vtt").exists()


def test_legacy_backfill_uses_narration_timing_without_an_aligner(monkeypatch, tmp_path):
    import json

    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)

    def no_aligner(items):
        raise AssertionError("no aligner is configured")

    monkeypatch.setattr(captions, "align_slides", no_aligner)
    module = {"module_number": 1, "video_path": str(video), "slides": slides}
    dry = captions.backfill_module_captions(module, apply=False)
    assert dry["status"] == "dry_run" and dry["method"] == "narration-timing-legacy"
    assert not video.with_suffix(".vtt").exists()
    result = captions.backfill_module_captions(module, apply=True)
    assert result == {"status": "generated", "module": 1, "method": "narration-timing-legacy"}
    cues = _vtt_cues(video.with_suffix(".vtt").read_text(encoding="utf-8"))
    assert [text for _, _, text in cues] == ["Slide 1 speaks.", "Slide 2 speaks."]
    # Slide 1 is 1.0 s of speech; slide 2 follows its 1.0 s transition pause.
    assert cues[0][:2] == pytest.approx((0.0, 1.0), abs=0.08)
    assert cues[1][:2] == pytest.approx((2.0, 3.5), abs=0.08)
    metadata = json.loads(video.with_suffix(".captions.json").read_text(encoding="utf-8"))
    assert metadata["method"] == "narration-timing-legacy"
    assert metadata["cue_count"] == 2
    assert metadata["vtt_sha256"] == captions.digest(video.with_suffix(".vtt"))
    assert abs(metadata["pause_seconds"] - 1.0) < 0.1
    assert cues[-1][1] <= metadata["duration"]
    again = captions.backfill_module_captions(module, apply=True)
    assert again["status"] == "skipped_valid_captions"
    generator = {**module, "video_service": {"run_id": "run-1"}}
    skipped = captions.backfill_module_captions(generator, apply=True)
    assert skipped["status"] == "skipped_video_generator"


def test_backfill_upgrades_narration_captions_once_an_aligner_is_configured(
    monkeypatch, tmp_path
):
    import json

    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    module = {"module_number": 1, "video_path": str(video), "slides": slides}
    assert captions.backfill_module_captions(module, apply=True)["status"] == "generated"
    metadata_path = video.with_suffix(".captions.json")
    assert json.loads(metadata_path.read_text())["method"] == "narration-timing-legacy"
    calls = []
    _fake_alignment(monkeypatch, calls)
    upgraded = captions.backfill_module_captions(module, apply=True)
    assert upgraded == {"status": "generated", "module": 1, "method": captions.LEGACY_METHOD}
    assert calls == [2]
    assert json.loads(metadata_path.read_text())["method"] == captions.LEGACY_METHOD
    again = captions.backfill_module_captions(module, apply=True)
    assert again["status"] == "skipped_valid_captions"
    monkeypatch.setattr(captions.settings, "caption_timing", "narration")
    kept = captions.backfill_module_captions(module, apply=True)
    assert kept["status"] == "skipped_valid_captions"
    assert calls == [2]
    assert json.loads(metadata_path.read_text())["method"] == captions.LEGACY_METHOD


def test_captions_off_writes_nothing(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    monkeypatch.setattr(captions.settings, "caption_timing", "off")
    module = {"module_number": 1, "video_path": str(video), "slides": slides}
    result = captions.backfill_module_captions(module, apply=True)
    assert result["status"] == "skipped_captions_off"
    assert captions.generate_legacy_module_captions(video, slides) == "skipped_captions_off"
    assert captions.generate_module_captions(video, slides) == "skipped_captions_off"
    assert not video.with_suffix(".vtt").exists()
    assert not video.with_suffix(".captions.json").exists()
    assert not video.with_suffix(".media.lock").exists()


def test_aligned_timing_without_an_aligner_fails_as_before(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    monkeypatch.setattr(captions.settings, "caption_timing", "aligned")
    with pytest.raises(CaptionsUnavailable, match="Configure CAPTION_ALIGN_COMMAND"):
        captions.generate_legacy_module_captions(video, slides)
    module = {"module_number": 1, "video_path": str(video), "slides": slides}
    failed = captions.backfill_module_captions(module, apply=True)
    assert failed["status"] == "unavailable" and "CAPTION_ALIGN_COMMAND" in failed["reason"]
    assert not video.with_suffix(".vtt").exists()


def test_a_comma_pause_is_not_taken_for_the_sentence_end(tmp_path):
    # Measured on real narration: "Next," paused, then "...actions." ran on with no pause.
    from app.generation.captions import narration_cues

    audio = tmp_path / "slide.wav"
    _speech(
        audio, [("tone", 1.4), ("quiet", 0.4), ("tone", 0.5), ("quiet", 0.3), ("tone", 5.8)]
    )
    start, end, pauses = _layout(audio, tmp_path, 8.4)
    assert pauses == [pytest.approx((1.45, 1.75)), pytest.approx((2.35, 2.55))]
    script = "Trust matters. Next, propose only approved actions. You must stick to solutions."
    cues = narration_cues(script, start, end, pauses)
    assert [cue["text"] for cue in cues] == [
        "Trust matters.",
        "Next, propose only approved actions.",
        "You must stick to solutions.",
    ]
    assert (cues[0]["start"], cues[0]["end"]) == pytest.approx((0.0, 1.45))
    # The sentence spans the comma's pause and ends near 5.6 s, not at the comma (2.35 s).
    assert cues[1]["start"] == pytest.approx(1.75)
    assert cues[1]["end"] == pytest.approx(5.6, abs=0.1)
    assert cues[2]["start"] == cues[1]["end"] and cues[2]["end"] == 8.4


def test_titles_and_latin_abbreviations_do_not_end_a_sentence():
    from app.generation.captions import _ends_sentence, narration_cues

    for word in ("Mr.", "Mrs.", "Ms.", "Dr.", "e.g.", "i.e.", "vs.", "(e.g.", "Dr.)"):
        assert not _ends_sentence(word), word
    for word in ("etc.", "report.", "why?", 'now."', "risk;"):
        assert _ends_sentence(word), word
    cues = narration_cues("Tell Mr. Raut, e.g. by email, etc. Then wait.", 0.0, 6.0)
    assert [cue["text"] for cue in cues] == ["Tell Mr. Raut, e.g. by email, etc.", "Then wait."]


def test_weak_word_check_ignores_leading_punctuation():
    from app.generation.captions import _balanced_pieces, _spoken_words

    words = _spoken_words(
        "Customers who want to open an account at the branch must provide (the original "
        "documents) for verification of the address and the identity."
    )
    timed = [{**word, "start": i * 0.1, "end": i * 0.1 + 0.1} for i, word in enumerate(words)]
    assert _balanced_pieces(timed)[0][-1]["text"] == "(the"
    assert _balanced_pieces(words, timed=False)[0][-1]["text"] == "provide"


def _failing_aligner(monkeypatch, error):
    from app.generation import captions

    def align(items):
        raise error

    monkeypatch.setattr(captions, "align_slides", align)
    _use_aligner(monkeypatch)


ALIGNER_ERRORS = [
    pytest.param(lambda: subprocess.TimeoutExpired("aligner", 600), id="timeout"),
    pytest.param(
        lambda: subprocess.CalledProcessError(1, "aligner"), id="worker-error"
    ),
    pytest.param(lambda: CaptionsUnavailable("Narration contains unalignable tokens"), id="tokens"),
    pytest.param(lambda: FileNotFoundError("aligner python"), id="missing-worker"),
]


@pytest.mark.parametrize("make_error", ALIGNER_ERRORS)
def test_auto_falls_back_to_narration_timing_when_alignment_fails(
    monkeypatch, tmp_path, caplog, make_error
):
    import json

    from app.generation import captions

    video, slides, _ = _rendered_module(
        tmp_path, monkeypatch, [([("tone", 1.5)], "Save the file.")]
    )
    _failing_aligner(monkeypatch, make_error())
    assert captions.generate_module_captions(video, slides) == "generated"
    metadata = json.loads(video.with_suffix(".captions.json").read_text(encoding="utf-8"))
    assert metadata["method"] == "narration-timing"
    assert "caption_alignment_failed" in caplog.text and "narration_timing" in caplog.text


def test_explicit_aligned_mode_does_not_fall_back(monkeypatch, tmp_path):
    import subprocess

    from app.generation import captions

    video, slides, _ = _rendered_module(
        tmp_path, monkeypatch, [([("tone", 1.5)], "Save the file.")]
    )
    _failing_aligner(monkeypatch, subprocess.TimeoutExpired("aligner", 600))
    monkeypatch.setattr(captions.settings, "caption_timing", "aligned")
    with pytest.raises(subprocess.TimeoutExpired):
        captions.generate_module_captions(video, slides)
    _failing_aligner(monkeypatch, CaptionsUnavailable("Aligner returned a different number"))
    with pytest.raises(CaptionsUnavailable, match="different number"):
        captions.generate_module_captions(video, slides)
    assert not video.with_suffix(".vtt").exists()


def test_failed_upgrade_keeps_existing_narration_captions(monkeypatch, tmp_path, caplog):
    from app.generation import captions

    video, slides, _ = _rendered_module(
        tmp_path, monkeypatch, [([("tone", 1.5)], "Save the file.")]
    )
    assert captions.generate_module_captions(video, slides) == "generated"
    files = [video.with_suffix(".vtt"), video.with_suffix(".captions.json")]
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in files]
    _failing_aligner(monkeypatch, CaptionsUnavailable("Aligner returned a different number"))
    assert captions.generate_module_captions(video, slides) == "kept_narration_captions"
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in files] == before
    assert "kept_narration_captions" in caplog.text


def test_legacy_auto_fallback_and_failed_upgrade(monkeypatch, tmp_path):
    import subprocess

    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    module = {"module_number": 1, "video_path": str(video), "slides": slides}
    _failing_aligner(monkeypatch, subprocess.TimeoutExpired("aligner", 600))
    result = captions.backfill_module_captions(module, apply=True)
    assert result == {"status": "generated", "module": 1, "method": "narration-timing-legacy"}
    kept = captions.backfill_module_captions(module, apply=True)
    assert kept == {
        "status": "kept_narration_captions",
        "module": 1,
        "method": "narration-timing-legacy",
    }


def test_corrupt_caption_metadata_is_regenerated(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides, _ = _rendered_module(
        tmp_path, monkeypatch, [([("tone", 1.5)], "Save the file.")]
    )
    for content in ("[]", '"text"', "3", "{"):
        video.with_suffix(".captions.json").write_text(content, encoding="utf-8")
        video.with_suffix(".vtt").write_text("WEBVTT\n", encoding="utf-8")
        assert captions.generate_module_captions(video, slides) == "generated"
    (tmp_path / "old").mkdir()
    legacy, legacy_slides = _legacy_module(tmp_path / "old", monkeypatch)
    legacy.with_suffix(".captions.json").write_text("[]", encoding="utf-8")
    legacy.with_suffix(".vtt").write_text("WEBVTT\n", encoding="utf-8")
    assert captions.generate_legacy_module_captions(legacy, legacy_slides) == "generated"


def test_backfill_reports_the_method_on_disk_and_planned_upgrades(monkeypatch, tmp_path):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch)
    module = {"module_number": 1, "video_path": str(video), "slides": slides}
    dry = captions.backfill_module_captions(module, apply=False)
    assert dry["existing_method"] is None and dry["would_upgrade"] is False
    captions.backfill_module_captions(module, apply=True)
    dry = captions.backfill_module_captions(module, apply=False)
    assert dry["existing_method"] == "narration-timing-legacy" and dry["would_upgrade"] is False
    _fake_alignment(monkeypatch)
    dry = captions.backfill_module_captions(module, apply=False)
    assert dry["method"] == captions.LEGACY_METHOD
    assert dry["existing_method"] == "narration-timing-legacy" and dry["would_upgrade"] is True
    assert captions.backfill_module_captions(module, apply=True)["method"] == (
        captions.LEGACY_METHOD
    )
    dry = captions.backfill_module_captions(module, apply=False)
    assert dry["would_upgrade"] is False
    # In narration mode the aligned captions on disk are kept and reported as such.
    monkeypatch.setattr(captions.settings, "caption_timing", "narration")
    skipped = captions.backfill_module_captions(module, apply=True)
    assert skipped == {
        "status": "skipped_valid_captions",
        "module": 1,
        "method": captions.LEGACY_METHOD,
    }


@pytest.mark.parametrize(
    ("repeats", "accepted"),
    [(5, True), (10, False), (2, False)],
    ids=["real-like-rate", "script-twice-as-long", "script-0.4x"],
)
def test_legacy_narration_refuses_a_script_edited_after_rendering(
    monkeypatch, tmp_path, repeats, accepted
):
    from app.generation import captions

    video, slides = _legacy_module(tmp_path, monkeypatch, narration=(6.0, 6.0))
    # 21 spoken characters per sentence: 5 of them over 6 s is 17.5 per second.
    for slide in slides:
        slide["script"] = " ".join(["Verify each document."] * 5)
    slides[1]["script"] = " ".join(["Verify each document."] * repeats)
    if accepted:
        assert captions.generate_legacy_module_captions(video, slides) == "generated"
        return
    with pytest.raises(CaptionsUnavailable, match="Slide 2 script does not match its narration"):
        captions.generate_legacy_module_captions(video, slides)
    assert not video.with_suffix(".vtt").exists()
    # Not a reason to fall back: the script itself is wrong.
    _failing_aligner(monkeypatch, CaptionsUnavailable("aligner down"))
    with pytest.raises(CaptionsUnavailable, match="Slide 2 script does not match"):
        captions.generate_legacy_module_captions(video, slides)


def test_short_slides_are_too_short_to_judge_a_rate():
    from app.generation.captions import _check_narration_length

    _check_narration_length(1, "Thank you.", 2.5)  # 10 characters in 2.5 s: 4 per second
    with pytest.raises(CaptionsUnavailable):
        _check_narration_length(1, "Thank you.", 4.0)


def test_rendered_videos_skip_the_length_check_their_hashes_already_prove(
    monkeypatch, tmp_path
):
    from app.generation import captions

    # 21 characters over 6 s would fail the legacy check; provenance binds script and audio.
    video, slides, _ = _rendered_module(
        tmp_path, monkeypatch, [([("tone", 6.0)], "Verify each document.")]
    )
    assert captions.generate_module_captions(video, slides) == "generated"
