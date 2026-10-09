"""Explicit, serial, provenance-checked caption backfill; dry-run by default."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.settings import settings
from app.generation.captions import check_video_source, generate_module_captions
from app.generation.runtime import load_course_for_generation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--module", required=True, type=int)
    parser.add_argument(
        "--apply", action="store_true", help="Generate captions; otherwise inspect only"
    )
    args = parser.parse_args()
    course = load_course_for_generation(args.course_id)
    module = next(
        (
            module
            for module in course.get("modules", [])
            if module.get("module_number") == args.module
        ),
        None,
    )
    if module is None:
        parser.error("Module does not exist")
    from app.core.storage import resolve_public_asset_path

    video = resolve_public_asset_path(str(module.get("video_path") or ""), settings)
    provenance = video.with_suffix(".source.json")
    if not video.is_file() or not provenance.is_file():
        print(json.dumps({"status": "requires_video_regeneration", "module": args.module}))
        return 1
    try:
        check_video_source(video, module.get("slides", []))
        if not args.apply:
            print(json.dumps({"status": "dry_run", "module": args.module, "video": str(video)}))
            return 0
        print(
            json.dumps(
                {"status": generate_module_captions(video, module["slides"]), "module": args.module}
            )
        )
        return 0
    except Exception as error:
        print(json.dumps({"status": "unavailable", "reason": str(error), "module": args.module}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
