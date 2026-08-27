"""Execute one course generation pipeline in an isolated worker process."""

from __future__ import annotations

import argparse
import logging
import sys

from app.core.logging import configure_logging
from app.core.settings import settings
from app.generation.runtime import run_full_course_generation
from app.repositories.schema import init_db

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--restart-from-blueprint", action="store_true")
    arguments = parser.parse_args()

    configure_logging(settings.log_level)
    init_db()
    try:
        run_full_course_generation(
            arguments.course_id,
            restart_from_blueprint=arguments.restart_from_blueprint,
        )
    except Exception as exc:
        logger.exception("pipeline_worker_failed course_id=%s", arguments.course_id)
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
