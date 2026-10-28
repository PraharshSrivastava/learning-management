"""Explicit, serial caption backfill for locally rendered module videos; dry-run by default.

Videos with render-time provenance use it. Older videos are captioned from their own
soundtrack once their slide boundaries are verified. Video Generator videos are skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.settings import settings
from app.generation.captions import backfill_module_captions
from app.generation.runtime import load_course_for_generation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--module", type=int, help="One module number; all modules by default")
    parser.add_argument(
        "--apply", action="store_true", help="Generate captions; otherwise inspect only"
    )
    args = parser.parse_args()
    if settings.video_generation_mode == "external":
        parser.error("The Video Generator is enabled; it supplies its own subtitles")
    course = load_course_for_generation(args.course_id)
    modules = [
        module
        for module in course.get("modules", [])
        if args.module is None or module.get("module_number") == args.module
    ]
    if not modules:
        parser.error("Module does not exist")
    failed = False
    # One module at a time: each alignment run holds the model in memory.
    for module in modules:
        result = backfill_module_captions(module, apply=args.apply)
        failed = failed or result["status"] == "unavailable"
        print(json.dumps(result), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
