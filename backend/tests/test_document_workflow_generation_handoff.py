"""Accepted inputs enter existing generation/recovery without PDF re-extraction."""

from contextlib import nullcontext
from types import SimpleNamespace

from app.core.settings import Settings
from app.services import generation


def service(course):
    return generation.GenerationService(
        SimpleNamespace(),
        Settings(),
        SimpleNamespace(get_draft_for_trainer=lambda *args: course),
    )


def test_fresh_builder_course_uses_normal_full_generation_reset(monkeypatch):
    calls = []
    monkeypatch.setattr(generation.generation_queue, "run", lambda **kwargs: nullcontext())
    monkeypatch.setattr(
        generation,
        "run_full_course_generation",
        lambda course_id, **kwargs: calls.append((course_id, kwargs)) or {},
    )
    service({"document_builder": {"origin": "accepted_revision"}}).generate_full_course(
        "c", "owner"
    )
    assert calls == [("c", {"restart_from_blueprint": True})]


def test_builder_blueprint_recovery_does_not_reextract_uploaded_pdf(monkeypatch):
    from app.repositories import courses

    calls = []
    course = {"course_id": "c", "document_builder": {"origin": "accepted_revision"}}
    monkeypatch.setattr(
        generation, "generation_state", lambda _: {"failed_checkpoint": "blueprint"}
    )
    monkeypatch.setattr(generation.generation_queue, "run", lambda **kwargs: nullcontext())
    monkeypatch.setattr(courses, "save_course", lambda *args: None)
    monkeypatch.setattr(
        generation,
        "generate_course_outline",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Accepted content must not be re-extracted")
        ),
    )
    monkeypatch.setattr(
        generation,
        "run_full_course_generation",
        lambda course_id, **kwargs: calls.append(kwargs) or course,
    )
    assert service(course).continue_generation("c", "owner") is course
    assert calls == [{"restart_from_blueprint": True}]
