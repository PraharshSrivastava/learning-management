"""Safe cleanup of generated files owned by one course."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from app.core.settings import Settings, settings
from app.core.storage import resolve_public_asset_path

logger = logging.getLogger(__name__)
_COURSE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_child(root: Path, child: Path) -> Path:
    resolved_root = root.resolve()
    resolved_child = child.resolve()
    if resolved_child == resolved_root or not resolved_child.is_relative_to(resolved_root):
        raise ValueError("Course artifact path escapes its configured storage directory")
    return resolved_child


def _thumbnail_stem(course_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", course_id).strip("-").lower()[:80]


def delete_course_artifacts(
    course_id: str,
    *,
    thumbnail_path: str | None = None,
    config: Settings = settings,
) -> list[str]:
    """Delete generated course assets and return paths that could not be removed."""
    if not _COURSE_ID_PATTERN.fullmatch(course_id):
        raise ValueError("Invalid course ID for artifact cleanup")

    directories = (
        _safe_child(config.image_dir, config.image_dir / course_id),
        _safe_child(config.audio_dir, config.audio_dir / f"course_{course_id}"),
        _safe_child(config.slide_dir, config.slide_dir / course_id),
        _safe_child(config.video_dir, config.video_dir / f"course_{course_id}"),
    )
    files: set[Path] = set()
    thumbnail_root = config.image_dir / "course_thumbnails"
    if thumbnail_root.is_dir():
        for candidate in thumbnail_root.glob(f"{_thumbnail_stem(course_id)}-*.png"):
            files.add(_safe_child(thumbnail_root, candidate))
    if thumbnail_path:
        candidate = resolve_public_asset_path(thumbnail_path, config)
        files.add(_safe_child(config.image_dir, candidate))

    failures: list[str] = []
    for directory in directories:
        try:
            if directory.exists():
                shutil.rmtree(directory)
        except OSError:
            failures.append(str(directory))
            logger.exception(
                "course_artifact_directory_cleanup_failed course_id=%s path=%s",
                course_id,
                directory,
            )
    for file_path in files:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            failures.append(str(file_path))
            logger.exception(
                "course_artifact_file_cleanup_failed course_id=%s path=%s",
                course_id,
                file_path,
            )
    return failures
