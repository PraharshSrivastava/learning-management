"""Move MP4 metadata to the front for fast progressive playback.

The operation is lossless: FFmpeg copies the existing audio/video streams and
atomically replaces only files whose ``moov`` atom currently follows ``mdat``.
"""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404
import sys
from pathlib import Path

import imageio_ffmpeg

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.settings import settings  # noqa: E402


def _atom_offset(path: Path, atom: bytes) -> int:
    overlap = len(atom) - 1
    offset = 0
    tail = b""
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            block = tail + chunk
            index = block.find(atom)
            if index >= 0:
                return offset - len(tail) + index
            tail = block[-overlap:]
            offset += len(chunk)
    return -1


def needs_faststart(path: Path) -> bool:
    moov_offset = _atom_offset(path, b"moov")
    mdat_offset = _atom_offset(path, b"mdat")
    return moov_offset >= 0 and mdat_offset >= 0 and moov_offset > mdat_offset


def optimize(path: Path) -> None:
    temporary_path = path.with_name(f".{path.name}.faststart.tmp.mp4")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-i",
        str(path),
        "-map",
        "0",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(temporary_path),
    ]
    try:
        result = subprocess.run(  # nosec B603
            command,
            capture_output=True,
            text=True,
            errors="ignore",
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"FFmpeg failed for {path}: {result.stderr}")
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--video-dir",
        type=Path,
        default=settings.video_dir,
        help="Directory containing generated MP4 files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report files requiring optimization without modifying them.",
    )
    args = parser.parse_args()

    video_dir = args.video_dir.resolve()
    candidates = sorted(video_dir.rglob("*.mp4")) if video_dir.is_dir() else []
    pending = [path for path in candidates if needs_faststart(path)]
    for path in pending:
        print(f"{'needs optimization' if args.check else 'optimizing'}: {path}")
        if not args.check:
            optimize(path)

    action = "require optimization" if args.check else "optimized"
    print(f"{len(pending)} of {len(candidates)} video(s) {action}")
    return 1 if args.check and pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
