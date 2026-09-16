from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.settings import settings
from app.services import courses as course_service_module
from app.services.course_artifacts import delete_course_artifacts
from app.services.courses import CourseService


class _DeletionRepository:
    def __init__(self, result: dict | None):
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def delete_for_trainer(self, course_id: str, trainer_id: str) -> dict | None:
        self.calls.append((course_id, trainer_id))
        return self.result


def test_delete_course_cleans_artifacts_and_notifies_affected_employees(monkeypatch) -> None:
    repository = _DeletionRepository(
        {
            "deleted": True,
            "thumbnail_path": "assets/images/course_thumbnails/course_1-hash.png",
            "affected_employee_ids": ["employee_1", "employee_2"],
        }
    )
    cleanup_calls: list[tuple[str, str | None]] = []
    broadcasts: list[str] = []
    monkeypatch.setattr(
        course_service_module,
        "delete_course_artifacts",
        lambda course_id, thumbnail_path=None: cleanup_calls.append(
            (course_id, thumbnail_path)
        )
        or [],
    )
    monkeypatch.setattr(
        course_service_module,
        "schedule_employee_broadcast",
        broadcasts.append,
    )

    CourseService(repository=repository).delete_course("course_1", "trainer_1")

    assert repository.calls == [("course_1", "trainer_1")]
    assert cleanup_calls == [
        ("course_1", "assets/images/course_thumbnails/course_1-hash.png")
    ]
    assert broadcasts == ["employee_1", "employee_2"]


def test_delete_course_hides_missing_or_foreign_course() -> None:
    with pytest.raises(NotFoundError, match="Course not found"):
        CourseService(repository=_DeletionRepository(None)).delete_course(
            "course_1", "trainer_2"
        )


def test_delete_course_rejects_active_generation(monkeypatch) -> None:
    repository = _DeletionRepository({"deleted": False, "generation_status": "running"})
    monkeypatch.setattr(
        course_service_module,
        "delete_course_artifacts",
        lambda *_args, **_kwargs: pytest.fail("active course artifacts must not be deleted"),
    )

    with pytest.raises(ConflictError, match="pending or running"):
        CourseService(repository=repository).delete_course("course_1", "trainer_1")


def test_delete_course_artifacts_removes_only_course_owned_outputs(tmp_path: Path) -> None:
    storage_dir = tmp_path / "storage"
    generated_dir = storage_dir / "generated"
    config = settings.model_copy(
        update={
            "storage_dir": storage_dir,
            "generated_dir": generated_dir,
            "upload_dir": storage_dir / "uploads",
            "image_dir": generated_dir / "images",
            "audio_dir": generated_dir / "audio",
            "slide_dir": generated_dir / "slides",
            "video_dir": generated_dir / "videos",
        }
    )
    course_id = "course_abc123"
    owned_directories = (
        config.image_dir / course_id,
        config.audio_dir / f"course_{course_id}",
        config.slide_dir / course_id,
        config.video_dir / f"course_{course_id}",
    )
    for directory in owned_directories:
        directory.mkdir(parents=True)
        (directory / "artifact.bin").write_bytes(b"course data")

    thumbnail = config.image_dir / "course_thumbnails" / f"{course_id}-hash.png"
    thumbnail.parent.mkdir(parents=True)
    thumbnail.write_bytes(b"thumbnail")
    other_course = config.video_dir / "course_course_other" / "module_1.mp4"
    other_course.parent.mkdir(parents=True)
    other_course.write_bytes(b"keep")
    source_document = config.upload_dir / "source.pdf"
    source_document.parent.mkdir(parents=True)
    source_document.write_bytes(b"keep")

    failures = delete_course_artifacts(
        course_id,
        thumbnail_path=f"assets/images/course_thumbnails/{thumbnail.name}",
        config=config,
    )

    assert failures == []
    assert all(not directory.exists() for directory in owned_directories)
    assert not thumbnail.exists()
    assert other_course.read_bytes() == b"keep"
    assert source_document.read_bytes() == b"keep"


def test_delete_course_artifacts_rejects_unsafe_course_id() -> None:
    with pytest.raises(ValueError, match="Invalid course ID"):
        delete_course_artifacts("../other-course")
