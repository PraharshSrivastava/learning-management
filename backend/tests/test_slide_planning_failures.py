from __future__ import annotations

import pytest

from app.core.providers import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionResponse,
)
from app.generation import slides as slides_module
from app.generation import video as video_module

SOURCE = "Log in with your employee ID. The dashboard shows leads, meetings and tasks."


def _course() -> dict:
    return {
        "course_id": "course_1",
        "course_name": "CRM Basics",
        "modules": [{"module_number": 1, "title": "Access", "source_text": SOURCE}],
    }


def _planned(module: dict) -> dict:
    module["planned_slides"] = [
        {"title": "Logging in", "slide_title": "Logging in", "content": ["Use your ID."]}
    ]
    return module


def _failed(module: dict) -> dict:
    module["planned_slides"] = []
    module["chain_of_thought"] = "Invalid JSON: EOF while parsing"
    return module


def _layouts(module: dict, *_args, **_kwargs) -> dict:
    module["slides"] = [dict(slide, layout_type="bullets") for slide in module["planned_slides"]]
    return module


def test_empty_plan_for_a_module_with_text_is_invalid() -> None:
    assert not slides_module._module_slides_are_valid(
        {"module_number": 1, "source_text": SOURCE, "planned_slides": []}
    )
    assert slides_module._module_slides_are_valid(
        {"module_number": 1, "source_text": "", "planned_slides": []}
    )


def test_failed_plan_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter([_failed, _planned])
    calls = []

    def plan(module, *_args, **_kwargs):
        calls.append(1)
        return next(replies)(module)

    monkeypatch.setattr(slides_module, "plan_slides_for_module", plan)
    monkeypatch.setattr(slides_module, "assign_layouts_to_module", _layouts)
    monkeypatch.setattr(slides_module, "log_event", lambda *_args, **_kwargs: None)
    course = _course()

    _, module = slides_module._generate_slides_for_module(
        course=course, module=course["modules"][0], index=0, base_url="u", model_name="m"
    )

    assert len(calls) == 2
    assert [slide["layout_type"] for slide in module["slides"]] == ["cover", "bullets"]


def test_module_fails_instead_of_shipping_a_cover_only_video(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(slides_module, "plan_slides_for_module", lambda m, *_a, **_k: _failed(m))
    monkeypatch.setattr(slides_module, "assign_layouts_to_module", _layouts)
    monkeypatch.setattr(slides_module, "log_event", lambda *_args, **_kwargs: None)
    course = _course()

    with pytest.raises(ValueError, match="Module 1 slide planning failed after 3 attempts"):
        slides_module._generate_slides_for_module(
            course=course, module=course["modules"][0], index=0, base_url="u", model_name="m"
        )


def test_cut_off_plan_is_reported_as_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def completion(**_kwargs):
        return ChatCompletionResponse(
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionMessage(content='{"chain_of_thought": "\t\t\t'),
                    finish_reason="length",
                )
            ]
        )

    monkeypatch.setattr(slides_module, "safe_chat_completion", completion)

    module = slides_module.plan_slides_for_module(
        {"module_number": 1, "title": "Access", "source_text": SOURCE}, "u", "m"
    )

    assert module["planned_slides"] == []
    assert "cut off" in module["chain_of_thought"]


def test_cover_only_detection() -> None:
    cover = {"layout_type": "cover", "is_cover_slide": True}
    assert slides_module.module_is_cover_only({"source_text": SOURCE, "slides": [cover]})
    assert not slides_module.module_is_cover_only(
        {"source_text": SOURCE, "slides": [cover, {"layout_type": "bullets"}]}
    )
    assert not slides_module.module_is_cover_only({"source_text": "", "slides": [cover]})


def test_regenerate_video_rebuilds_a_cover_only_module(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generation import html, runtime, scripts, tts

    state = {"rebuilt": False}
    steps = []

    def load(_course_id):
        slides = [{"layout_type": "cover", "is_cover_slide": True}]
        if state["rebuilt"]:
            slides.append({"layout_type": "bullets"})
        return {"course_id": "course_1", "modules": [{"source_text": SOURCE, "slides": slides}]}

    def rebuild_slides(course_id, module_number):
        steps.append(("slides", module_number))
        state["rebuilt"] = True

    monkeypatch.setattr(runtime, "load_course_for_generation", load)
    monkeypatch.setattr(runtime, "save_generated_course", lambda *_a, **_k: None)
    monkeypatch.setattr(slides_module, "generate_slides_for_single_module", rebuild_slides)
    monkeypatch.setattr(
        scripts,
        "generate_scripts_for_single_module",
        lambda _c, number: steps.append(("scripts", number)),
    )
    monkeypatch.setattr(
        tts, "generate_tts_for_course", lambda _c, modules: steps.append(("tts", modules))
    )
    monkeypatch.setattr(html, "compile_slides_for_course", lambda _c: steps.append(("html", None)))
    rendered = []
    monkeypatch.setattr(
        video_module,
        "render_video_for_module",
        lambda course, _c, _n: rendered.append(len(course["modules"][0]["slides"])) or "v.mp4",
    )

    assert video_module.generate_video_for_module("course_1", 1) == "v.mp4"
    assert steps == [("slides", 1), ("scripts", 1), ("tts", {1}), ("html", None)]
    assert rendered == [2]


def test_regenerate_video_refreshes_stale_audio_for_that_module_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.generation import html, runtime, tts

    steps = []
    course = {
        "course_id": "course_1",
        "modules": [
            {"source_text": SOURCE, "slides": [{"layout_type": "cover"}, {"layout_type": "bullets"}]}
        ]
        * 2,
    }
    monkeypatch.setattr(runtime, "load_course_for_generation", lambda _c: course)
    monkeypatch.setattr(runtime, "save_generated_course", lambda *_a, **_k: None)
    monkeypatch.setattr(
        slides_module,
        "generate_slides_for_single_module",
        lambda *_a: pytest.fail("a module with content slides must not be re-planned"),
    )
    monkeypatch.setattr(
        tts, "generate_tts_for_course", lambda _c, modules: steps.append(("tts", modules))
    )
    monkeypatch.setattr(html, "compile_slides_for_course", lambda _c: steps.append(("html", None)))
    monkeypatch.setattr(video_module, "render_video_for_module", lambda *_a: "v.mp4")

    video_module.generate_video_for_module("course_1", 2)

    assert steps == [("tts", {2}), ("html", None)]
