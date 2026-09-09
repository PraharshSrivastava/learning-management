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
