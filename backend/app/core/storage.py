"""Filesystem layout and public-path mapping for local development storage."""

from __future__ import annotations

from pathlib import Path

from app.core.settings import Settings


def ensure_storage_directories(config: Settings) -> None:
    """Create writable local directories during startup, never during import."""
    directories = (
        config.storage_dir,
        config.generated_dir,
        config.upload_dir,
        config.derived_document_dir,
        config.image_dir,
        config.audio_dir,
        config.slide_dir,
        config.video_dir,
        config.static_dir / "brand",
        config.template_dir / "layouts",
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def public_asset_url(category: str, *parts: object) -> str:
    """Return the stable client-facing URL path for generated/static content."""
    suffix = "/".join(str(part).strip("/\\") for part in parts)
    return f"assets/{category}/{suffix}" if suffix else f"assets/{category}"


def resolve_public_asset_path(value: str, config: Settings) -> Path:
    """Resolve a stored ``assets/<category>/...`` URL to its local filesystem path."""
    normalized = str(value or "").replace("\\", "/").lstrip("/")
    prefix, separator, remainder = normalized.partition("/")
    if prefix != "assets" or not separator:
        path = Path(value)
        return path if path.is_absolute() else config.backend_dir / path

    category, separator, relative = remainder.partition("/")
    roots = {
        "audio": config.audio_dir,
        "brand": config.static_dir / "brand",
        "images": config.image_dir,
        "layouts": config.template_dir / "layouts",
        "slides": config.slide_dir,
        "videos": config.video_dir,
    }
    root = roots.get(category)
    if root is None:
        raise ValueError(f"Unsupported public asset category: {category}")
    return root / relative if separator else root
