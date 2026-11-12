"""Per-course Video Engine choice: image detection, recommendation, storage and API rules."""

from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from docx import Document
from docx.shared import Inches
from PIL import Image

from app.core.exceptions import ConflictError, DomainValidationError
from app.core.settings import Settings, settings
from app.modules.courses.schemas import CourseResponse, CourseUpdateRequest
from app.modules.courses.service import CourseService
from app.modules.generation.pipeline import video_engine
from app.modules.generation.pipeline.blueprint import extract_images_from_pdf

SECRET = "s" * 40


def png(width: int, height: int, color: str = "blue") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def engine_on(monkeypatch):
    monkeypatch.setattr(settings, "video_engine_toggle_enabled", True)
    monkeypatch.setattr(settings, "video_service_base_url", "http://127.0.0.1:8090")
    monkeypatch.setattr(settings, "video_service_hmac_secret", SECRET)


@pytest.fixture
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.modules.generation.pipeline.blueprint.IMAGE_DIR", str(tmp_path / "images"))
    monkeypatch.setattr("app.documents.docx.IMAGE_DIR", str(tmp_path / "images"))
    return tmp_path


# --- PDF detection -------------------------------------------------------------------------


def _pdf(path, pages: int, logo: bool, screenshot_on: set[int] = frozenset(), icon: bool = False):
    logo_png = png(120, 40, "red")
    with fitz.open() as document:
        for number in range(1, pages + 1):
            page = document.new_page(width=595, height=842)
            page.insert_text((72, 120), f"Page {number} body text about the process.")
            if logo:
                # Letterhead logo in the top band of every page.
                page.insert_image(fitz.Rect(40, 15, 160, 55), stream=logo_png)
            if icon:
                page.insert_image(fitz.Rect(72, 300, 92, 320), stream=png(20, 20, "green"))
            if number in screenshot_on:
                page.insert_image(fitz.Rect(72, 200, 520, 520), stream=png(900, 640, "gray"))
        document.save(path)
    return str(path)


def test_pdf_with_only_a_repeated_logo_has_no_meaningful_images(image_dir):
    pdf = _pdf(image_dir / "text.pdf", pages=4, logo=True, icon=True)
    images = extract_images_from_pdf(pdf, "c-text")

    assert images, "the logo and icon are still extracted for slides"
    assert all(image["decorative"] for image in images)
    assert video_engine.meaningful_image_count({"images": images}) == 0
    assert video_engine.recommended_video_engine({"images": images}) is True


def test_pdf_with_one_screenshot_recommends_standard_generation(image_dir):
    pdf = _pdf(image_dir / "guide.pdf", pages=4, logo=True, screenshot_on={3})
    images = extract_images_from_pdf(pdf, "c-guide")

    screenshots = [image for image in images if not image["decorative"]]
    assert len(screenshots) == 1
    assert screenshots[0]["page"] == 3
    assert video_engine.meaningful_image_count({"images": images}) == 1
    assert video_engine.recommended_video_engine({"images": images}) is False


def test_pdf_classification_rules():
    sizes = {page: (600.0, 800.0) for page in range(1, 11)}
    records = [
        {"xref": 1, "page": 1, "bbox": (50, 300, 550, 600)},  # screenshot
        {"xref": 2, "page": 1, "bbox": (50, 300, 80, 330)},  # icon: under 40 pt
        {"xref": 3, "page": 2, "bbox": (50, 740, 300, 790)},  # footer band
        {"xref": 4, "page": 2, "bbox": (50, 300, 140, 380)},  # 90x80 = 1.5% of the page
        *({"xref": 5, "page": page, "bbox": (100, 300, 500, 600)} for page in range(1, 6)),
    ]
    video_engine.classify_pdf_images(records, sizes, total_pages=10)
    decorative = [record["decorative"] for record in records]

    # xref 5 repeats on 5 of 10 pages (50%), so it is a letterhead-style repeat.
    assert decorative == [False, True, True, False, True, True, True, True, True]


# --- DOCX detection ------------------------------------------------------------------------


def test_docx_marks_small_and_repeated_images_decorative(image_dir):
    from app.documents.docx import extract_docx_blueprint_source

    path = image_dir / "guide.docx"
    document = Document()
    logo = BytesIO(png(200, 60, "red"))
    for heading in ("Overview", "Steps", "Summary"):
        document.add_paragraph(heading)
        logo.seek(0)
        document.add_picture(logo, width=Inches(1.5))
        document.add_paragraph(f"{heading} body text for the course.")
    document.add_picture(BytesIO(png(32, 32, "green")), width=Inches(0.3))
    document.add_picture(BytesIO(png(1280, 720, "gray")), width=Inches(6))
    document.save(path)

    _metadata, _lines, images = extract_docx_blueprint_source(str(path), "c-docx")

    meaningful = [image for image in images if not image["decorative"]]
    assert len(meaningful) == 1
    assert meaningful[0]["width"] == 1280
    assert video_engine.meaningful_image_count({"images": images}) == 1


def test_docx_without_images_recommends_video_engine(image_dir):
    from app.documents.docx import extract_docx_blueprint_source

    path = image_dir / "text.docx"
    document = Document()
    document.add_paragraph("Customer due diligence")
    document.add_paragraph("Collect and verify identity documents before onboarding.")
    document.save(path)

    _metadata, _lines, images = extract_docx_blueprint_source(str(path), "c-docx-text")
    assert images == []
    assert video_engine.recommended_video_engine({"images": images}) is True


# --- Counting, engine resolution and outline defaults --------------------------------------


def test_meaningful_count_dedupes_course_and_module_images():
    shot = {"image_id": "img_1", "decorative": False}
    course = {
        "images": [shot, {"image_id": "logo", "decorative": True}],
        "modules": [{"images": [shot]}, {"images": [{"image_id": "img_2"}]}],
    }
    # img_1 once, img_2 has no flag (older course) so it counts, the logo does not.
    assert video_engine.meaningful_image_count(course) == 2


def test_course_engine_resolution(engine_on, monkeypatch):
    monkeypatch.setattr(settings, "video_generation_mode", "external")
    assert video_engine.course_uses_video_engine({"video_engine": False}) is False
    assert video_engine.course_uses_video_engine({"video_engine": True}) is True
    # Older courses keep the engine their videos came from.
    legacy_service = {"modules": [{"video_service": {"run_id": "r1"}}]}
    legacy_local = {"modules": [{"video_path": "assets/videos/c/m1.mp4"}]}
    monkeypatch.setattr(settings, "video_generation_mode", "local")
    assert video_engine.course_uses_video_engine(legacy_service) is True
    monkeypatch.setattr(settings, "video_generation_mode", "external")
    assert video_engine.course_uses_video_engine(legacy_local) is False
    # No videos yet: the server default.
    assert video_engine.course_uses_video_engine({"modules": [{}]}) is True


def test_switched_off_toggle_restores_the_server_wide_mode(monkeypatch):
    monkeypatch.setattr(settings, "video_engine_toggle_enabled", False)
    monkeypatch.setattr(settings, "video_generation_mode", "local")
    assert video_engine.course_uses_video_engine({"video_engine": True}) is False

    course = {"images": []}
    video_engine.apply_outline_recommendation(course)
    assert "video_engine" not in course
    assert "video_engine_recommendation" not in course


@pytest.mark.parametrize(
    ("images", "expected_engine"),
    [([], True), ([{"image_id": "img_1", "decorative": False}], False)],
)
def test_outline_defaults_to_the_recommendation(engine_on, images, expected_engine):
    course = {"images": images, "modules": []}
    video_engine.apply_outline_recommendation(course)

    assert course["video_engine"] is expected_engine
    assert course["video_engine_recommendation"] == {
        "recommended": expected_engine,
        "image_count": len(images),
    }


def test_outline_without_a_configured_service_defaults_to_standard(monkeypatch):
    monkeypatch.setattr(settings, "video_engine_toggle_enabled", True)
    monkeypatch.setattr(settings, "video_service_base_url", None)
    course = {"images": []}
    video_engine.apply_outline_recommendation(course)

    assert course["video_engine"] is False
    assert course["video_engine_recommendation"]["recommended"] is True


def test_course_response_carries_engine_and_recommendation(engine_on):
    response = CourseResponse.model_validate(
        {
            "course_id": "c1",
            "trainer_id": "t1",
            "status": "draft",
            "video_engine": False,
            "video_engine_recommendation": {"recommended": False, "image_count": 6},
        }
    )
    assert response.video_engine is False
    assert response.video_engine_recommended is False
    assert response.meaningful_image_count == 6


# --- Settings ------------------------------------------------------------------------------


def test_toggle_is_on_without_any_env_setting():
    assert Settings().video_engine_toggle_enabled is True


def test_production_requires_tts_while_trainers_can_choose_the_engine():
    with pytest.raises(ValueError, match="TTS_ENDPOINT"):
        Settings(
            app_env="production",
            video_generation_mode="external",
            video_service_base_url="http://127.0.0.1:8090",
            video_service_hmac_secret=SECRET,
            tts_endpoint="",
            llm_api_key="k",
            database_url="postgresql://x/y",
            cors_allowed_origins="https://lms.example",
            hub_launch_dev_mode=True,
        )


# --- Switching the engine on a course ------------------------------------------------------


class FakeRepository:
    def __init__(self, course: dict, *, running: bool = False):
        self.course = course
        self.running = running
        self.saved: list[tuple[dict, bool]] = []

    def get_draft_for_trainer(self, course_id, trainer_id):
        return self.course

    def save_draft(self, course, *, release_generation_worker=False):
        if release_generation_worker and self.running:
            raise ConflictError(
                "Course generation is already running. "
                "Wait for it to finish before editing the blueprint."
            )
        self.saved.append((dict(course), release_generation_worker))


def _course(**extra):
    return {
        "course_id": "c1",
        "trainer_id": "t1",
        "status": "draft",
        "video_engine": True,
        "modules": [{"module_number": 1, "title": "M1", "source_text": "Text"}],
        **extra,
    }


def _switch(repository, value):
    return CourseService(repository).update_course(
        "c1", CourseUpdateRequest(video_engine=value), "t1"
    )


def test_switching_without_generated_content_keeps_the_blueprint(engine_on):
    repository = FakeRepository(_course())
    course = _switch(repository, False)

    assert course["video_engine"] is False
    assert course["modules"][0]["title"] == "M1"
    assert repository.saved[-1][1] is True  # saved through the running-generation guard


def test_switching_with_generated_content_clears_it(engine_on):
    generated = _course(thumbnail_path="assets/thumbs/c1.png")
    generated["modules"][0].update(
        {"notes": "Notes", "video_path": "assets/videos/c1/m1.mp4", "quiz": {"questions": []}}
    )
    course = _switch(FakeRepository(generated), False)

    assert course["video_engine"] is False
    assert "video_path" not in course["modules"][0]
    assert "notes" not in course["modules"][0]
    assert "thumbnail_path" not in course
    assert course["generation"]["status"] == "pending"


def test_same_engine_is_not_a_change(engine_on):
    generated = _course()
    generated["modules"][0]["video_path"] = "assets/videos/c1/m1.mp4"
    repository = FakeRepository(generated)
    course = _switch(repository, True)

    assert course["modules"][0]["video_path"] == "assets/videos/c1/m1.mp4"
    assert repository.saved[-1][1] is False


def test_switching_during_generation_is_refused(engine_on):
    with pytest.raises(ConflictError, match="before switching engines"):
        _switch(FakeRepository(_course(), running=True), False)


def test_turning_on_without_a_configured_service_is_refused(engine_on, monkeypatch):
    monkeypatch.setattr(settings, "video_service_base_url", None)
    with pytest.raises(DomainValidationError, match="isn't available"):
        _switch(FakeRepository(_course(video_engine=False)), True)


def test_switching_is_refused_when_the_toggle_is_off(engine_on, monkeypatch):
    monkeypatch.setattr(settings, "video_engine_toggle_enabled", False)
    with pytest.raises(ConflictError, match="not enabled"):
        _switch(FakeRepository(_course()), False)


def test_blueprint_save_without_engine_leaves_it_alone(engine_on):
    repository = FakeRepository(_course())
    CourseService(repository).update_course(
        "c1", CourseUpdateRequest(course_name="Renamed"), "t1"
    )
    assert repository.course["video_engine"] is True


def test_blueprint_re_extraction_keeps_the_trainers_choice(engine_on):
    course = {"images": []}  # text-only: the default would be Video Engine on
    video_engine.apply_outline_recommendation(course, existing_choice=False)

    assert course["video_engine"] is False
    assert course["video_engine_recommendation"]["recommended"] is True


# --- Continue after a switch or a later-stage failure ---------------------------------------

LOCAL_WAVE = ("thumbnail", "quiz", "notes", "slides")
SERVICE_WAVE = ("thumbnail", "quiz", "notes")


def _resumable(generation, **module):
    course = _course(video_engine=False, generation=generation)
    course["modules"][0].update({"num_questions": 3, **module})
    return course


def test_continue_reruns_missing_wave_outputs_after_a_later_failure(engine_on):
    # The big-coding case: slides, scripts and audio survived, thumbnail/quiz/notes did not,
    # and the course failed at video. Continue used to skip Wave 1 and fail at publish.
    from app.modules.generation.pipeline.runtime import wave_stages_to_resume

    course = _resumable(
        {"status": "failed", "failed_checkpoint": "video"},
        slides=[{"slide_number": 1, "title": "One"}],
    )

    assert wave_stages_to_resume(course, LOCAL_WAVE) == ("thumbnail", "quiz", "notes")


def test_continue_reruns_failed_wave_stages_even_if_output_exists(engine_on, monkeypatch):
    from app.modules.generation.pipeline import runtime

    monkeypatch.setattr(runtime, "missing_generation_outputs", lambda course: [])
    course = _resumable(
        {"status": "failed", "failed_checkpoint": "wave_1", "failed_stages": ["quiz"]}
    )

    assert runtime.wave_stages_to_resume(course, LOCAL_WAVE) == ("quiz",)


def test_continue_with_complete_wave_outputs_skips_wave_1(engine_on, monkeypatch):
    from app.modules.generation.pipeline import runtime

    monkeypatch.setattr(runtime, "missing_generation_outputs", lambda course: ["video"])
    course = _resumable({"status": "failed", "failed_checkpoint": "video"})

    assert runtime.wave_stages_to_resume(course, LOCAL_WAVE) == ()


def test_video_engine_course_never_resumes_slides(engine_on):
    from app.modules.generation.pipeline.runtime import wave_stages_to_resume

    course = _resumable({"status": "failed", "failed_checkpoint": "video"})
    course["video_engine"] = True

    assert wave_stages_to_resume(course, SERVICE_WAVE) == SERVICE_WAVE


def test_switching_clears_a_checkpoint_from_the_other_engine(engine_on):
    # No generated files yet, but a failed run planned for the Video Engine is on record.
    stale = _course(
        generation={
            "status": "failed",
            "failed_checkpoint": "wave_1",
            "failed_stages": ["thumbnail"],
            "stages": {"blueprint": {"status": "completed"}, "thumbnail": {"status": "failed"}},
        }
    )
    course = _switch(FakeRepository(stale), False)

    assert course["generation"]["status"] == "pending"
    assert "failed_checkpoint" not in course["generation"]
    assert course["generation"]["stages"] == {"blueprint": {"status": "completed"}}
    assert course["modules"][0]["title"] == "M1"


def test_switching_a_fresh_blueprint_keeps_its_state(engine_on):
    fresh = _course(generation={"status": "completed", "stages": {"blueprint": {"status": "completed"}}})
    course = _switch(FakeRepository(fresh), False)

    assert course["generation"]["status"] == "completed"
