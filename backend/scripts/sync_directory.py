"""Run Hub directory sync from the command line."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.directory_sync import bootstrap_full_directory, sync_directory_changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync LMS employees from Hub directory exports.")
    parser.add_argument("mode", choices=["full", "incremental"])
    parser.add_argument("--after-id", type=int, default=None)
    args = parser.parse_args()

    if args.mode == "full":
        result = bootstrap_full_directory()
    else:
        result = sync_directory_changes(after_id=args.after_id)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
