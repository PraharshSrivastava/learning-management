from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

from app.core.exceptions import ProviderError
from app.core.providers import LLMClient
from app.generation import blueprint
from app.generation.runtime import PipelineStageError
from app.services.uploads import UploadService


def _llm_response(content: dict) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(content)),
                finish_reason="stop",
            )
        ]
    )


def test_upload_service_accepts_pdf_pptx_and_docx(tmp_path, monkeypatch) -> None:
    saved: list[dict] = []

    def fake_save_document(trainer_id: str, file_name: str, file_path: str) -> dict:
        document = {
            "document_id": f"document_{len(saved) + 1}",
            "trainer_id": trainer_id,
            "file_name": file_name,
            "file_path": file_path,
            "created_at": f"2026-01-01T00:00:0{len(saved)}",
        }
        saved.append(document)
        return document

    monkeypatch.setattr("app.services.uploads.save_document_record", fake_save_document)
    monkeypatch.setattr("app.services.uploads.list_document_records", lambda trainer_id=None: saved)

    service = UploadService(tmp_path)
    service.save_document("guide.pdf", io.BytesIO(b"pdf"), "trainer_1")
    service.save_document("slides.pptx", io.BytesIO(b"pptx"), "trainer_1")
    service.save_document("handbook.docx", io.BytesIO(b"docx"), "trainer_1")

    files = service.list_documents("trainer_1")
    assert {item.file_type for item in files} == {"pdf", "pptx", "docx"}
    assert {item.display_name for item in files} == {
        "guide.pdf",
        "slides.pptx",
        "handbook.docx",
    }


def test_upload_service_rejects_unsupported_extension(tmp_path) -> None:
    service = UploadService(tmp_path)

    with pytest.raises(ValueError, match="Only PDF, PPTX, and DOCX files are supported"):
        service.save_document("notes.txt", io.BytesIO(b"text"), "trainer_1")


def test_shared_module_extractor_sends_complete_document_text(monkeypatch) -> None:
    user_messages: list[str] = []

    def fake_safe_chat_completion(**kwargs):
        user_messages.append(kwargs["messages"][1]["content"])
        return _llm_response(
            {
                "modules": [
                    {
                        "module_number": 1,
                        "title": "Introduction",
                        "start_line": 1,
                        "num_questions": 3,
                    }
                ],
            }
        )

    monkeypatch.setattr(blueprint, "safe_chat_completion", fake_safe_chat_completion)
    monkeypatch.setattr(blueprint, "get_llm_endpoint", lambda purpose=None: ("http://llm", "model"))

    tail_marker = "PPTX_TAIL_MARKER"
    body_lines = ["A" * 51_000, tail_marker]
    blueprint.extract_modules_with_llm(body_lines, course_id="document")

    assert tail_marker in user_messages[0]


def test_module_extraction_schema_excludes_chain_of_thought() -> None:
    schema = blueprint.ModuleListSchema.model_json_schema()

    assert "chain_of_thought" not in schema["properties"]
    assert schema["required"] == ["modules"]


def test_pptx_runner_uses_shared_module_extractor_and_ignores_images(
    monkeypatch,
) -> None:
    calls: list[tuple[list[str], str]] = []

    monkeypatch.setattr(
        blueprint,
        "extract_text_from_pptx",
        lambda path: ["Course title", "Introduction", "Details"],
    )
    monkeypatch.setattr(
        blueprint,
        "extract_pptx_metadata_with_llm",
        lambda lines, course_id: {
            "course_name": "PPTX Course",
            "course_description": "Description",
            "course_objective": "Objective",
            "course_difficulty": "Beginner",
            "language": "English",
            "target_audience": "Employees",
        },
    )

    def fake_extract_modules(
        body_lines: list[str],
        course_id: str = "blueprint",
    ) -> list[dict]:
        calls.append((body_lines, course_id))
        return [
            {
                "module_number": 1,
                "title": "Introduction",
                "start_line": 1,
                "num_questions": 3,
            }
        ]

    monkeypatch.setattr(blueprint, "extract_modules_with_llm", fake_extract_modules)
    result = blueprint.run_pptx_blueprint_extraction("slides.pptx", course_id="course_1")

    assert calls == [(["Course title", "Introduction", "Details"], "course_1")]
    assert result["course_name"] == "PPTX Course"
    assert result["images"] == []


def test_generate_course_outline_dispatches_pptx_without_calling_pdf_runner(
    tmp_path, monkeypatch
) -> None:
    pptx_path = tmp_path / "slides.pptx"
    pptx_path.write_bytes(b"pptx")
    document = {
        "document_id": "document_1",
        "trainer_id": "trainer_1",
        "file_name": "slides.pptx",
    }
    calls: list[str] = []
    outline = {
        "course_name": "PPTX Course",
        "course_description": "",
        "course_objective": "",
        "course_difficulty": "",
        "language": "",
        "target_audience": "",
        "modules": [],
        "images": [],
    }

    monkeypatch.setattr(blueprint, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        blueprint,
        "get_document_by_file_name",
        lambda filename, trainer_id=None: document,
    )
    monkeypatch.setattr(blueprint, "get_all_courses", lambda status: [])
    monkeypatch.setattr(blueprint, "save_course", lambda course, status: None)
    monkeypatch.setattr(blueprint, "mark_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(blueprint, "log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(blueprint, "complete_generation", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        blueprint,
        "run_blueprint_extraction",
        lambda path, course_id: pytest.fail("PDF runner must not handle PPTX"),
    )
    monkeypatch.setattr(
        blueprint,
        "run_pptx_blueprint_extraction",
        lambda path, course_id: calls.append(path) or dict(outline),
    )

    result = blueprint.generate_course_outline(
        "slides.pptx", course_id="course_1", trainer_id="trainer_1"
    )

    assert calls == [str(pptx_path)]
    assert result["course_name"] == "PPTX Course"


def test_generate_course_outline_converts_docx_then_uses_pdf_runner(tmp_path, monkeypatch) -> None:
    docx_path = tmp_path / "handbook.docx"
    derived_pdf = tmp_path / "derived.pdf"
    docx_path.write_bytes(b"docx")
    derived_pdf.write_bytes(b"pdf")
    document = {
        "document_id": "document_2",
        "trainer_id": "trainer_1",
        "file_name": "handbook.docx",
    }
    calls: list[tuple[str, str]] = []
    outline = {
        "course_name": "DOCX Course",
        "course_description": "",
        "course_objective": "",
        "course_difficulty": "",
        "language": "",
        "target_audience": "",
        "modules": [],
        "images": [],
    }

    monkeypatch.setattr(blueprint, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        blueprint,
        "get_document_by_file_name",
        lambda filename, trainer_id=None: document,
    )
    monkeypatch.setattr(blueprint, "get_all_courses", lambda status: [])
    monkeypatch.setattr(blueprint, "save_course", lambda course, status: None)
    monkeypatch.setattr(blueprint, "mark_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(blueprint, "log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(blueprint, "complete_generation", lambda *args, **kwargs: None)
    monkeypatch.setattr(blueprint.settings, "derived_document_dir", tmp_path)
    monkeypatch.setattr(blueprint, "convert_office_to_pdf", lambda source, target: derived_pdf)
    monkeypatch.setattr(
        blueprint,
        "run_blueprint_extraction",
        lambda path, course_id: calls.append((path, course_id)) or dict(outline),
    )

    result = blueprint.generate_course_outline(
        "handbook.docx", course_id="course_2", trainer_id="trainer_1"
    )

    assert calls == [(str(derived_pdf), "course_2")]
    assert result["course_name"] == "DOCX Course"


def test_llm_client_rejects_oversized_input_without_truncating() -> None:
    client = LLMClient(
        base_url="http://llm",
        model="model",
        api_key=None,
        context_window=128_000,
        max_input_tokens=100,
        max_output_tokens=28_000,
    )

    with pytest.raises(ProviderError, match="request was not truncated"):
        client.complete([{"role": "user", "content": "x" * 6_000}])


def test_llm_client_sends_thinking_flag(monkeypatch) -> None:
    captured_payload: dict = {}

    class Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {"content": "{}"},
                        "finish_reason": "stop",
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        del url, headers, timeout
        captured_payload.update(json)
        return Response()

    monkeypatch.setattr("app.core.providers.requests.post", fake_post)
    client = LLMClient(
        base_url="http://llm",
        model="model",
        api_key=None,
        context_window=128_000,
        max_input_tokens=100_000,
        max_output_tokens=28_000,
        enable_thinking=False,
    )

    client.complete([{"role": "user", "content": "Return JSON."}])

    assert captured_payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_llm_client_rejects_null_message_content(monkeypatch) -> None:
    class Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {"content": None},
                        "finish_reason": "length",
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        del url, headers, json, timeout
        return Response()

    monkeypatch.setattr("app.core.providers.requests.post", fake_post)
    client = LLMClient(
        base_url="http://llm",
        model="model",
        api_key=None,
        context_window=128_000,
        max_input_tokens=100_000,
        max_output_tokens=28_000,
        enable_thinking=False,
    )

    with pytest.raises(PipelineStageError, match="message.content was null.*finish_reason=length"):
        client.complete([{"role": "user", "content": "Return JSON."}], attempts=1)


def test_pptx_text_extraction_reads_text_frames_and_tables(tmp_path) -> None:
    pptx = pytest.importorskip("pptx")
    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "Safety Training"
    text_box = slide.shapes.add_textbox(0, 0, 1_000_000, 1_000_000)
    text_box.text = "Wear protective equipment. Follow instructions."
    table_shape = slide.shapes.add_table(1, 2, 0, 0, 2_000_000, 500_000)
    table_shape.table.cell(0, 0).text = "Audience"
    table_shape.table.cell(0, 1).text = "Operators"
    path = tmp_path / "training.pptx"
    presentation.save(path)

    lines = blueprint.extract_text_from_pptx(str(path))

    assert "Safety Training" in lines
    assert "Wear protective equipment." in lines
    assert "Follow instructions." in lines
    assert "Audience | Operators" in lines
