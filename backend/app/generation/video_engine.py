"""Per-course choice between the Video Generator ("Video Engine") and standard generation.

A course's source images decide the recommended engine: the Video Generator does not use
document images, so a course with any meaningful image or screenshot is recommended for
standard generation, and a text-only course for the Video Engine. Logos, letterheads, icons
and other decorative images do not count.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from app.core.settings import settings

# A PDF image is decorative when its box is under this share of the page area ...
PDF_MIN_AREA_FRACTION = 0.015
# ... or either side is shorter than this many points ...
PDF_MIN_SIDE_POINTS = 40.0
# ... or it sits entirely inside this top or bottom band of the page ...
PDF_EDGE_BAND_FRACTION = 0.08
# ... or the same image repeats on at least this many pages and this share of pages.
REPEAT_MIN_PAGES = 3
REPEAT_MIN_PAGE_FRACTION = 0.5
# A DOCX image is decorative under this many pixels on either side, or when it repeats.
DOCX_MIN_SIDE_PIXELS = 64
DOCX_REPEAT_MIN_USES = 3


def classify_pdf_images(
    records: list[dict[str, Any]],
    page_sizes: dict[int, tuple[float, float]],
    total_pages: int,
) -> None:
    """Set ``decorative`` on each extracted PDF image record, in place.

    ``page_sizes`` maps a 1-based page number to its (width, height) in points, and each
    record carries ``page``, ``bbox`` and ``xref``.
    """
    pages_by_xref: dict[Any, set[int]] = {}
    for record in records:
        pages_by_xref.setdefault(record.get("xref"), set()).add(int(record.get("page") or 0))
    for record in records:
        record["decorative"] = _pdf_record_is_decorative(
            record, page_sizes, total_pages, pages_by_xref
        )


def _pdf_record_is_decorative(
    record: dict[str, Any],
    page_sizes: dict[int, tuple[float, float]],
    total_pages: int,
    pages_by_xref: dict[Any, set[int]],
) -> bool:
    xref = record.get("xref")
    if xref is not None:
        pages = len(pages_by_xref.get(xref, ()))
        if (
            pages >= REPEAT_MIN_PAGES
            and total_pages > 0
            and pages / total_pages >= REPEAT_MIN_PAGE_FRACTION
        ):
            return True
    bbox = record.get("bbox")
    size = page_sizes.get(int(record.get("page") or 0))
    if not bbox or len(bbox) != 4 or not size:
        return False
    x0, y0, x1, y1 = (float(value) for value in bbox)
    page_width, page_height = size
    width, height = max(0.0, x1 - x0), max(0.0, y1 - y0)
    if width < PDF_MIN_SIDE_POINTS or height < PDF_MIN_SIDE_POINTS:
        return True
    if page_width > 0 and page_height > 0:
        if (width * height) / (page_width * page_height) < PDF_MIN_AREA_FRACTION:
            return True
        band = page_height * PDF_EDGE_BAND_FRACTION
        if y1 <= band or y0 >= page_height - band:
            return True
    return False


def classify_docx_images(records: list[dict[str, Any]], uses: dict[str, int]) -> None:
    """Set ``decorative`` on each extracted DOCX image record, in place.

    ``uses`` maps a record's ``sha256`` to how many times the document places that image.
    """
    for record in records:
        width = int(record.get("width") or 0)
        height = int(record.get("height") or 0)
        small = (0 < width < DOCX_MIN_SIDE_PIXELS) or (0 < height < DOCX_MIN_SIDE_PIXELS)
        repeated = uses.get(str(record.get("sha256") or ""), 1) >= DOCX_REPEAT_MIN_USES
        record["decorative"] = small or repeated


def _course_images(course: dict) -> Iterable[dict]:
    for image in course.get("images") or []:
        if isinstance(image, dict):
            yield image
    for module in course.get("modules") or []:
        if not isinstance(module, dict):
            continue
        for image in module.get("images") or []:
            if isinstance(image, dict):
                yield image


def meaningful_image_count(course: dict) -> int:
    """Unique course images that would add something for learners.

    Courses made before this feature have no ``decorative`` flags, so all their images count.
    """
    seen: set[str] = set()
    count = 0
    for index, image in enumerate(_course_images(course)):
        key = str(image.get("image_id") or image.get("file_path") or f"#{index}")
        if key in seen:
            continue
        seen.add(key)
        if image.get("decorative") is not True:
            count += 1
    return count


def recommended_video_engine(course: dict) -> bool:
    return meaningful_image_count(course) == 0


def toggle_enabled() -> bool:
    return bool(settings.video_engine_toggle_enabled)


def video_engine_available() -> bool:
    return bool(settings.video_service_base_url) and len(
        settings.video_service_hmac_secret or ""
    ) >= 32


def course_uses_video_engine(course: dict) -> bool:
    """The engine a course's videos are made with.

    A stored trainer choice wins. A course from before this feature keeps the engine its
    existing videos came from, and otherwise follows ``VIDEO_GENERATION_MODE``. With the
    toggle switched off (``VIDEO_ENGINE_TOGGLE_ENABLED=false``) every course follows
    ``VIDEO_GENERATION_MODE``, as before this feature.
    """
    if not toggle_enabled():
        return settings.video_generation_mode == "external"
    stored = course.get("video_engine")
    if isinstance(stored, bool):
        return stored
    modules = [module for module in course.get("modules") or [] if isinstance(module, dict)]
    if any((module.get("video_service") or {}).get("run_id") for module in modules):
        return True
    if any(module.get("video_path") for module in modules):
        return False
    return settings.video_generation_mode == "external"


def apply_outline_recommendation(course: dict, existing_choice: Any = None) -> None:
    """Store the recommendation on a new course and use it as the default engine.

    existing_choice is a choice the trainer already made for this course (a blueprint
    re-extraction keeps it).
    """
    if not toggle_enabled():
        return
    count = meaningful_image_count(course)
    recommended = count == 0
    course["video_engine_recommendation"] = {"recommended": recommended, "image_count": count}
    course["video_engine"] = (
        existing_choice
        if isinstance(existing_choice, bool)
        else recommended and video_engine_available()
    )


def video_engine_fields(course: dict) -> dict[str, Any]:
    """Response fields the trainer app uses for the toggle and its recommendation."""
    stored = course.get("video_engine_recommendation")
    if isinstance(stored, dict) and isinstance(stored.get("image_count"), int):
        count = stored["image_count"]
    else:
        count = meaningful_image_count(course)
    return {
        "video_engine": course_uses_video_engine(course),
        "video_engine_recommended": count == 0,
        "meaningful_image_count": count,
    }


def docx_image_uses(rids_in_order: list[str], sha_by_rid: dict[str, str]) -> dict[str, int]:
    """How many times each image (by content hash) is placed in a DOCX body."""
    counter: Counter[str] = Counter()
    for rid in rids_in_order:
        sha = sha_by_rid.get(rid)
        if sha:
            counter[sha] += 1
    return dict(counter)
