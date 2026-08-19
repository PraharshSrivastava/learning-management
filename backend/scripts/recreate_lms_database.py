"""Recreate LMS database tables and clear generated/uploaded storage."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.settings import settings  # noqa: E402
from app.core.storage import ensure_storage_directories  # noqa: E402
from app.repositories.database import close_pool  # noqa: E402
from app.repositories.schema import recreate_db  # noqa: E402

CONFIRMATION = "RECREATE_LMS_DATABASE"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drop/recreate LMS tables without seeded identities and clear LMS storage."
    )
    parser.add_argument(
        "--confirm",
        required=True,
        help=f"Must be exactly {CONFIRMATION!r}.",
    )
    return parser.parse_args()


def _storage_targets() -> tuple[Path, ...]:
    return (
        settings.upload_dir,
        settings.derived_document_dir,
        settings.image_dir,
        settings.audio_dir,
        settings.slide_dir,
        settings.video_dir,
    )


def _safe_target(target: Path) -> Path:
    storage_root = settings.storage_dir.resolve()
    resolved = target.resolve()
    if resolved == storage_root:
        raise ValueError(f"Refusing to clear LMS_STORAGE_DIR itself: {resolved}")
    try:
        resolved.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError(f"Refusing to clear path outside LMS_STORAGE_DIR: {resolved}") from exc
    return resolved


def _clear_storage() -> int:
    ensure_storage_directories(settings)
    removed = 0
    for target in _storage_targets():
        resolved = _safe_target(target)
        if not resolved.exists():
            continue
        for child in resolved.iterdir():
            if child.name == ".keep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed += 1
    return removed


def main() -> int:
    args = _parse_args()
    if args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing to run without --confirm {CONFIRMATION}")
    recreate_db()
    removed = _clear_storage()
    close_pool()
    print("Recreated LMS database schema with no seeded identities.")
    print(f"Cleared LMS storage entries: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
