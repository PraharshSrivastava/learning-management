from __future__ import annotations

from app.services.courses import CourseService


def test_merge_modules_accepts_dict_payload_from_course_update() -> None:
    existing = [
        {
            "module_number": 1,
            "title": "Logging in to PhillipX CRM",
            "source_text": "old text",
            "start_line": "1",
            "video_path": "/assets/videos/module_1.mp4",
            "end_line": "99",
        }
    ]
    incoming = [
        {
            "title": "Logging in to PhillipX CRM",
            "source_text": "updated text",
            "start_line": "1",
            "num_questions": 3,
        }
    ]

    merged = CourseService._merge_modules(existing, incoming)

    assert merged == [
        {
            "module_number": 1,
            "title": "Logging in to PhillipX CRM",
            "source_text": "updated text",
            "start_line": "1",
            "num_questions": 3,
            "video_path": "/assets/videos/module_1.mp4",
        }
    ]
