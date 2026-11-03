import base64
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

from PIL import Image

from app.generation import thumbnails


def _course() -> dict:
    return {
        "course_id": "course-1",
        "course_name": "Incident Response",
        "course_description": "Learn the incident response lifecycle.",
    }


def test_prompt_failure_writes_placeholder_without_retry(monkeypatch, tmp_path: Path):
    planner = Mock(side_effect=RuntimeError("planner unavailable"))
    monkeypatch.setattr(thumbnails, "THUMBNAIL_DIR", str(tmp_path))
    monkeypatch.setattr(thumbnails, "THUMBNAILS_ENABLED", True)
    monkeypatch.setattr(thumbnails, "_planned_thumbnail_prompt", planner)

    path = thumbnails.generate_course_thumbnail(_course(), "course-1", attempts=3)

    planner.assert_called_once()
    output = tmp_path / path.rsplit("/", 1)[-1]
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (1024, 1024)


def test_image_failure_writes_placeholder_without_retry(monkeypatch, tmp_path: Path):
    post = Mock(side_effect=RuntimeError("image model unavailable"))
    monkeypatch.setattr(thumbnails, "THUMBNAIL_DIR", str(tmp_path))
    monkeypatch.setattr(thumbnails, "THUMBNAILS_ENABLED", True)
    monkeypatch.setattr(thumbnails, "_planned_thumbnail_prompt", lambda *args, **kwargs: "A globe")
    monkeypatch.setattr(thumbnails.requests, "post", post)

    path = thumbnails.generate_course_thumbnail(_course(), "course-1", attempts=3)

    post.assert_called_once()
    assert (tmp_path / path.rsplit("/", 1)[-1]).stat().st_size > 0


def test_qwen_image_payload_sends_steps_without_openai_only_params(monkeypatch):
    monkeypatch.setattr(thumbnails, "THUMBNAIL_ENDPOINT", "http://gateway/v1/images/generations")
    monkeypatch.setattr(thumbnails, "THUMBNAIL_MODEL", "qwen-image-2.1")

    payload = thumbnails._thumbnail_request_payload("A glass funnel")

    assert payload == {
        "model": "qwen-image-2.1",
        "prompt": "A glass funnel",
        "size": "1024x1024",
        "num_inference_steps": 40,
    }


def test_flux_payload_sends_only_model_prompt_and_size(monkeypatch):
    monkeypatch.setattr(thumbnails, "THUMBNAIL_ENDPOINT", "http://gateway/v1/images/generations")
    monkeypatch.setattr(thumbnails, "THUMBNAIL_MODEL", "flux-3-image-klein")

    payload = thumbnails._thumbnail_request_payload("A glass funnel")

    assert payload == {"model": "flux-3-image-klein", "prompt": "A glass funnel", "size": "1024x1024"}


def test_other_gateway_models_keep_openai_params(monkeypatch):
    monkeypatch.setattr(thumbnails, "THUMBNAIL_ENDPOINT", "http://gateway/v1/images/generations")
    monkeypatch.setattr(thumbnails, "THUMBNAIL_MODEL", "z-image-turbo")

    payload = thumbnails._thumbnail_request_payload("A glass funnel")

    assert payload["n"] == 1
    assert payload["response_format"] == "b64_json"


def test_thumbnail_prompt_adds_style_and_bans_text():
    prompt = thumbnails._thumbnail_prompt_from_subject("A glass funnel on a plain surface")

    assert prompt.startswith("A glass funnel on a plain surface. ")
    assert thumbnails.THUMBNAIL_STYLE in prompt
    assert "no text, letters, numbers" in prompt


def test_text_bearing_subject_is_replanned_with_feedback(monkeypatch):
    replies = iter(
        [
            "Two gears labeled 'Dividend' and 'Share Price' on a plain surface",
            "A translucent glass funnel narrowing into a single bright stream",
        ]
    )
    requests_sent = []

    def completion(base_url, model, messages, **kwargs):
        requests_sent.append(json.loads(messages[1]["content"]))
        message = Mock(content=json.dumps({"subject": next(replies)}))
        return Mock(choices=[Mock(message=message)])

    monkeypatch.setattr(thumbnails, "get_llm_endpoint", lambda stage: ("http://llm", "model"))
    monkeypatch.setattr(thumbnails, "safe_chat_completion", completion)

    prompt = thumbnails._planned_thumbnail_prompt("Corporate Actions", "Dividends", "course-1")

    assert prompt.startswith("A translucent glass funnel narrowing into a single bright stream. ")
    assert "rejected_subjects" not in requests_sent[0]
    assert requests_sent[1]["rejected_subjects"] == [
        "Two gears labeled 'Dividend' and 'Share Price' on a plain surface"
    ]


def test_text_bearing_subject_pattern():
    for subject in (
        "A brass gavel resting beside a folded newspaper",
        "A magnifying glass over a stack of currency notes",
        "A sleek order book displaying buy and sell columns",
        "A red candlestick chart object on a plain surface",
    ):
        assert thumbnails._TEXT_BEARING_SUBJECT.search(subject)
    assert not thumbnails._TEXT_BEARING_SUBJECT.search(
        "A green leaf sprouting from a cracked concrete block"
    )


def test_model_image_is_saved_as_compressed_webp(monkeypatch, tmp_path: Path):
    source = BytesIO()
    Image.new("RGBA", (1024, 1024), (40, 90, 160, 255)).save(source, format="PNG")
    response = Mock()
    response.json.return_value = {"data": [{"b64_json": base64.b64encode(source.getvalue()).decode()}]}
    monkeypatch.setattr(thumbnails, "THUMBNAIL_DIR", str(tmp_path))
    monkeypatch.setattr(thumbnails, "THUMBNAILS_ENABLED", True)
    monkeypatch.setattr(thumbnails, "_planned_thumbnail_prompt", lambda *args, **kwargs: "A globe")
    monkeypatch.setattr(thumbnails.requests, "post", Mock(return_value=response))

    path = thumbnails.generate_course_thumbnail(_course(), "course-1")

    assert path.endswith(".webp")
    with Image.open(tmp_path / path.rsplit("/", 1)[-1]) as image:
        assert image.format == "WEBP"
        assert image.size == (1024, 1024)
    # A second call reuses the stored file instead of generating again.
    assert thumbnails.generate_course_thumbnail(_course(), "course-1") == path
