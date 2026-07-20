def _ready_draft_course():
    return {
        "id": "thumbnail-course-1",
        "course_name": "Data Privacy Basics",
        "course_description": "How employees should handle customer data.",
        "created_at": 123,
        "modules": [
            {
                "module_number": 1,
                "title": "Handling sensitive data",
                "video_path": "assets/videos/privacy.mp4",
                "quiz": {
                    "questions": [
                        {
                            "question_text": "What should you do with customer data?",
                            "options": [
                                {"key": "A", "text": "Protect it"},
                                {"key": "B", "text": "Share it"},
                            ],
                            "correct_option": "A",
                        }
                    ]
                },
            }
        ],
    }


def test_sync_clean_database_generates_course_thumbnail(database, monkeypatch):
    from pipelines import exporter

    database.save_all_courses([_ready_draft_course()], "draft")

    calls = []

    def fake_generate(course, course_id):
        calls.append((course["course_name"], course_id))
        return "assets/images/course_thumbnails/thumbnail-course-1.png"

    monkeypatch.setattr(exporter, "generate_course_thumbnail", fake_generate)

    exporter.sync_clean_database()

    published = database.get_all_courses("published")
    drafts = database.get_all_courses("draft")

    assert calls == [("Data Privacy Basics", "thumbnail-course-1")]
    assert published[0]["thumbnail"] == "assets/images/course_thumbnails/thumbnail-course-1.png"
    assert published[0]["thumbnail_url"] == "assets/images/course_thumbnails/thumbnail-course-1.png"
    assert published[0]["thumbnail_prompt_hash"]
    assert drafts[0]["thumbnail"] == "assets/images/course_thumbnails/thumbnail-course-1.png"
    assert drafts[0]["thumbnail_prompt_hash"] == published[0]["thumbnail_prompt_hash"]


def test_thumbnail_generator_resolves_relative_image_urls(monkeypatch):
    from pipelines import thumbnail_generator

    requested_urls = []

    class FakeResponse:
        content = b"fake-image-bytes"

        def raise_for_status(self):
            pass

    def fake_get(url, timeout):
        requested_urls.append((url, timeout))
        return FakeResponse()

    monkeypatch.setattr(thumbnail_generator.requests, "get", fake_get)

    image_bytes = thumbnail_generator._decode_image_payload(
        {"data": [{"url": "/v1/images/generated-image/content"}]},
        "http://35.238.33.238:30010/v1/images/generations",
    )

    assert image_bytes == b"fake-image-bytes"
    assert requested_urls == [
        ("http://35.238.33.238:30010/v1/images/generated-image/content", 120)
    ]


def test_thumbnail_generator_decodes_prediction_image_b64():
    from pipelines import thumbnail_generator

    image_bytes = thumbnail_generator._decode_image_payload(
        {"predictions": [{"image_b64": "ZmFrZS1pbWFnZS1ieXRlcw=="}]}
    )

    assert image_bytes == b"fake-image-bytes"


def test_thumbnail_prompt_is_used_directly_from_llm(monkeypatch):
    from pipelines import thumbnail_generator
    from pipelines.prompts import COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT

    class FakeMessage:
        content = (
            '{"prompt":"Modern corporate learning thumbnail showing abstract CRM workflow '
            'symbols, customer relationship nodes, subtle blue lighting, polished illustration"}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    captured_messages = []

    monkeypatch.setattr(
        thumbnail_generator,
        "get_llm_endpoint",
        lambda: ("http://fake-llm/v1", "fake-model"),
    )
    monkeypatch.setattr(
        thumbnail_generator,
        "safe_chat_completion",
        lambda base_url, model, messages, **kwargs: (
            captured_messages.extend(messages) or FakeResponse()
        ),
    )

    prompt = thumbnail_generator._planned_thumbnail_prompt(
        "PhillipX CRM",
        "A user manual for lead management, customer engagement, and sales operations.",
    )

    assert prompt == (
        "Modern corporate learning thumbnail showing abstract CRM workflow "
        "symbols, customer relationship nodes, subtle blue lighting, polished illustration"
    )
    assert captured_messages[0]["content"] == COURSE_THUMBNAIL_PROMPT_PLANNER_SYSTEM_PROMPT
