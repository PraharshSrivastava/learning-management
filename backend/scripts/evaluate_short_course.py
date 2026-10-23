"""Opt-in live generation check with isolated JSON persistence, never PostgreSQL.

Run from backend with a synthetic PDF only:
  .venv/Scripts/python.exe -m scripts.evaluate_short_course --source ../tmp/qwen-short-flow/short-training.pdf --output ../tmp/qwen-short-flow/run
Uses real generation stages and configured remote providers. Local repository
adapters intentionally exclude production persistence, HTTP auth and learner UI.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
from pathlib import Path
import shutil
import threading
import time
from contextlib import nullcontext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--model", default="qwen3.6-35b")
    parser.add_argument("--thinking", choices=("true", "false", ""), default="false",
                        help="LLM_ENABLE_THINKING; empty sends no flag (provider default)")
    parser.add_argument("--stub-tts", action="store_true",
                        help="Serve local tone WAVs instead of calling TTS (when the TTS server is down)")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Read only provider values; never load the deployment database credentials.
    root = Path(__file__).resolve().parents[2]
    provider_keys = {
        "LLM_API_KEY", "LITELLM_API_KEY", "LLM_BASE_URL", "TTS_ENDPOINT",
        "TTS_MODEL_NAME", "TTS_VOICE", "TTS_TEMPERATURE", "TTS_SPEED",
        "COURSE_THUMBNAIL_ENDPOINT", "COURSE_THUMBNAIL_MODEL", "COURSE_THUMBNAIL_API_KEY",
    }
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key in provider_keys:
            os.environ.setdefault(key, value.strip().strip("\"'"))
    os.environ.update({
        "APP_ENV": "development", "DATABASE_URL": "", "LANGFUSE_ENABLED": "false",
        "LLM_MODEL_NAME": args.model, "LLM_ENABLE_THINKING": args.thinking,
        "LMS_STORAGE_DIR": str(output / "storage"),
        "LMS_GENERATED_DIR": str(output / "generated"),
        "LMS_UPLOAD_DIR": str(output / "uploads"),
        "LMS_DERIVED_DOCUMENT_DIR": str(output / "derived_documents"),
        "LMS_IMAGE_DIR": str(output / "generated/images"),
        "LMS_AUDIO_DIR": str(output / "generated/audio"),
        "LMS_SLIDE_DIR": str(output / "generated/slides"),
        "LMS_VIDEO_DIR": str(output / "generated/videos"),
        "GENERATION_LLM_STAGE_WORKERS": "1",
        "COURSE_THUMBNAIL_CONNECT_TIMEOUT": "20", "COURSE_THUMBNAIL_READ_TIMEOUT": "90",
        "CAPTION_ALIGN_COMMAND": "[]",
    })
    ffmpeg = root / "backend/.venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
    if ffmpeg.is_file():
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", str(ffmpeg))
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(root / "tmp/qwen-short-flow/browsers"))

    from app.core.settings import settings
    from app.core.logging import configure_logging
    from app.repositories import courses, database, documents
    import requests

    configure_logging("INFO")
    warnings = []

    class WarningCapture(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                message = record.getMessage()
                for secret in (settings.llm_api_key, settings.thumbnail_api_key):
                    if secret:
                        message = message.replace(secret, "[REDACTED]")
                warnings.append(message[:700])

    logging.getLogger().addHandler(WarningCapture())
    for path in (settings.upload_dir, settings.image_dir, settings.audio_dir, settings.slide_dir, settings.video_dir):
        path.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, settings.upload_dir / source.name)
    lock = threading.RLock()
    course_path = output / "course.json"
    store = {"course": json.loads(course_path.read_text()) if args.resume else None}

    def persist():
        course_path.write_text(json.dumps(store["course"], indent=2), encoding="utf-8")

    def get_course(course_id, status=None):
        with lock:
            c = store["course"]
            if c and c["course_id"] == course_id and (status is None or c.get("status") == status):
                return copy.deepcopy(c)
            return None

    def get_all_courses(status=None):
        c = store["course"]
        result = get_course(c["course_id"], status) if c else None
        return [result] if result else []

    def save_course(course, status):
        with lock:
            store["course"] = copy.deepcopy(course)
            store["course"]["status"] = status
            persist()

    def patch_fields(course_id, course, *, course_fields=(), module_fields=()):
        with lock:
            target = store["course"]
            assert target and target["course_id"] == course_id
            for field in course_fields:
                if field in course:
                    target[field] = copy.deepcopy(course[field])
                else:
                    target.pop(field, None)
            by_number = {m["module_number"]: m for m in course.get("modules", [])}
            for module in target.get("modules", []):
                updated = by_number[module["module_number"]]
                for field in module_fields:
                    if field in updated:
                        module[field] = copy.deepcopy(updated[field])
                    else:
                        module.pop(field, None)
            persist()

    def patch_state(course_id, update):
        with lock:
            assert store["course"]["course_id"] == course_id
            update(store["course"])
            persist()
            return copy.deepcopy(store["course"])

    def no_database(*args, **kwargs):
        raise AssertionError("Live database access is prohibited in this evaluation")

    class LocalRepository:
        get_draft = staticmethod(lambda course_id: get_course(course_id, "draft"))
        save_draft = staticmethod(lambda course: save_course(course, "draft"))

    courses.get_course = get_course
    courses.get_all_courses = get_all_courses
    courses.save_course = save_course
    courses.save_all_courses = lambda values, status: [save_course(c, status) for c in values]
    courses.delete_course = lambda course_id: store.update(course=None)
    courses.patch_generated_course_fields = patch_fields
    courses.patch_generation_state = patch_state
    courses.CourseRepository = LocalRepository
    database.get_connection = no_database
    database.advisory_lock = lambda name: nullcontext()
    documents.get_document_by_file_name = lambda *a: {
        "document_id": "synthetic-qwen-short", "trainer_id": "local-evaluation",
        "file_name": source.name, "file_path": str(settings.upload_dir / source.name),
    }
    # Keep outbound metadata, not authorization headers or prompt content.
    physical_calls = []
    original_post = requests.post

    def stub_speech(text):
        # Words at ~2.5/s; a quiet tone keeps duration/silence checks meaningful.
        import io, math, struct, wave
        rate, seconds = 24000, max(1.0, len(text.split()) / 2.5)
        frames = b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 220 * i / rate)))
                          for i in range(int(rate * seconds)))
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(frames)
        response = requests.Response()
        response.status_code, response._content = 200, buffer.getvalue()
        return response

    def observed_post(url, **kwargs):
        payload = kwargs.get("json", {})
        started = time.monotonic()
        row = {"endpoint": url, "model": payload.get("model")}
        if args.stub_tts and "audio/speech" in url:
            row.update(stub=True, http_status=200, seconds=0)
            with lock:
                physical_calls.append(row)
            return stub_speech(payload.get("input", ""))
        if "chat/completions" in url:
            row.update(thinking=payload.get("chat_template_kwargs", {}).get("enable_thinking"), max_tokens=payload.get("max_tokens"))
            assert row["thinking"] == settings.llm_enable_thinking
        if "audio/speech" in url:
            kwargs["timeout"] = 120
        elif "chat/completions" in url:
            kwargs["timeout"] = 90
        try:
            response = original_post(url, **kwargs)
            row["http_status"] = response.status_code
            if response.ok and "chat/completions" in url:
                body = response.json()
                row.update(usage=body.get("usage"), finish_reason=body["choices"][0].get("finish_reason"))
            return response
        except requests.RequestException as exc:
            row["error"] = type(exc).__name__
            raise
        finally:
            row["seconds"] = round(time.monotonic() - started, 2)
            with lock:
                physical_calls.append(row)
            print(json.dumps({"provider_call": row}), flush=True)

    requests.post = observed_post
    from app.generation.blueprint import generate_course_outline
    from app.generation import runtime, video
    original_capture = video.capture_slide_frames

    def capture_and_keep(html_file, *, slide_count, output_dir):
        frames = original_capture(html_file, slide_count=slide_count, output_dir=output_dir)
        preview = output / "preview" / Path(html_file).stem
        preview.mkdir(parents=True, exist_ok=True)
        for frame in frames:
            shutil.copyfile(frame, preview / Path(frame).name)
        return frames

    video.capture_slide_frames = capture_and_keep
    report = {
        "model": settings.llm_model_name, "thinking": settings.llm_enable_thinking,
        "source": str(source), "source_kind": "synthetic", "database": "isolated-json-adapter",
        "deployment_changed": False, "physical_calls": physical_calls, "stub_tts": args.stub_tts,
        "not_tested": ["PostgreSQL persistence", "HTTP upload/authentication", "trainer approval UI", "assignment", "employee player UI"],
    }
    started = time.monotonic()
    try:
        course_id = "qwen-short-flow-local"
        if not args.resume:
            outline = generate_course_outline(source.name, course_id=course_id, trainer_id="local-evaluation")
            for module in outline["modules"]:
                module["num_questions"] = 2
            save_course(outline, "draft")
            print(json.dumps({"blueprint_modules": len(outline["modules"])}), flush=True)
        course = runtime.run_full_course_generation(course_id, restart_from_blueprint=not args.resume)
        report.update(status="completed", missing_outputs=runtime.missing_generation_outputs(course))
    except Exception as exc:
        message = str(exc)
        for secret in (settings.llm_api_key, settings.thumbnail_api_key):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        report.update(status="failed", error_type=type(exc).__name__, error=message[:1500])
    finally:
        course = store["course"] or {}
        report.update(seconds=round(time.monotonic()-started,2), warnings=warnings,
                      stages=course.get("generation", {}).get("stages", {}),
                      local_lifecycle=course.get("status"),
                      modules=[{"title": m.get("title"), "slides": len(m.get("slides", [])),
                                "quiz_questions": len(m.get("quiz", {}).get("questions", [])),
                                "audio_files": sum(bool(s.get("audio_path")) for s in m.get("slides", [])),
                                "video": m.get("video_path")} for m in course.get("modules", [])])
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("status", "seconds", "modules", "local_lifecycle")}), flush=True)
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
