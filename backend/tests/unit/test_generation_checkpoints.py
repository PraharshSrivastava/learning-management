"""Generation checkpoint state bookkeeping."""

from app.generation.runtime import (
    _merge_generated_course,
    generation_state,
    mark_stage,
    recover_interrupted_generations,
)


def test_worker_output_merge_preserves_latest_checkpoint_state():
    latest = {
        "id": "course-1",
        "modules": [{"title": "Module 1"}],
        "generation": {
            "status": "failed",
            "failed_checkpoint": "wave_1",
            "failed_stages": ["quiz"],
            "stages": {"quiz": {"status": "failed"}},
        },
    }
    stale_worker_output = {
        "id": "course-1",
        "modules": [{"title": "Module 1", "notes": "Generated notes"}],
        "generation": {"status": "running", "stages": {"notes": {"status": "running"}}},
    }

    merged = _merge_generated_course(latest, stale_worker_output)

    assert merged["modules"][0]["notes"] == "Generated notes"
    assert merged["generation"] == latest["generation"]


def test_mark_stage_tracks_the_current_downstream_checkpoint():
    course = {"id": "course-1", "modules": []}

    mark_stage(course, "thumbnail", "running")
    mark_stage(course, "quiz", "running")
    mark_stage(course, "slides", "running")

    state = generation_state(course)
    assert state["current_checkpoint"] == "slides"

    mark_stage(course, "quiz", "completed")

    assert state["current_checkpoint"] == "slides"

    mark_stage(course, "thumbnail", "failed", error="timeout")

    assert state["current_checkpoint"] is None
    assert state["failed_checkpoint"] == "thumbnail"


def test_recover_interrupted_wave_one_preserves_failed_stage_list(database):
    from app.repositories.courses import CourseRepository

    course = {
        "id": "interrupted-course",
        "course_name": "Interrupted Course",
        "modules": [],
        "generation": {
            "status": "running",
            "current_checkpoint": "wave_1",
            "stages": {
                "thumbnail": {"status": "running"},
                "quiz": {"status": "running"},
                "notes": {"status": "completed"},
                "slides": {"status": "running"},
            },
        },
    }
    CourseRepository().save_draft(course)

    recover_interrupted_generations()

    recovered = CourseRepository().get_draft("interrupted-course")
    state = recovered["generation"]
    assert state["status"] == "failed"
    assert state["current_checkpoint"] == "wave_1"
    assert state["failed_checkpoint"] == "wave_1"
    assert state["failed_stages"] == ["thumbnail", "quiz", "slides"]
    assert state["stages"]["notes"]["status"] == "completed"
