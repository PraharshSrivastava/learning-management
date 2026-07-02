import json
import os
import tempfile
from filelock import FileLock


def atomic_write_json(path, data, indent=2):
    """
    Write JSON to `path` atomically and safely under concurrent access:
    1. Acquire an exclusive lock on a sibling `.lock` file (blocks any other
       writer using the same lock until this write finishes or the 30s
       timeout is hit).
    2. Write to a temp file in the same directory, flush and fsync it.
    3. Atomically replace the target file with the temp file.
    This prevents both truncated/corrupted files (from a crash mid-write)
    and lost writes (from two requests writing the same file at once) —
    critical since courses_draft.json and courses.json are the single
    source of truth with no database behind them.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    lock_path = os.path.abspath(path) + ".lock"
    lock = FileLock(lock_path, timeout=30)
    with lock:
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
