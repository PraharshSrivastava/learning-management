"""Repair legacy builder image metadata; default is a read-only preview.

Run inside the LMS backend: python repair_builder_course_images.py --apply --render
Only builder-owned image references and the affected videos/HTML are changed.
"""

import argparse
import copy
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from psycopg.types.json import Jsonb

from app.core.settings import settings
from app.core.storage import public_asset_url, resolve_public_asset_path
from app.repositories.courses import get_course
from app.repositories.database import get_connection


def repair_images(apply=False, render=False):
    if render and not apply:
        raise ValueError("--render requires --apply")
    backup = (
        settings.storage_dir
        / "maintenance"
        / ("builder-images-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    )
    results = []
    with get_connection() as db:
        courses = db.execute(
            "SELECT course_id FROM courses WHERE metadata_json->'document_builder'->>'origin' = 'accepted_revision'"
        ).fetchall()
    for item in courses:
        cid = item["course_id"]
        with get_connection() as db:
            course = db.execute(
                "SELECT * FROM courses WHERE course_id = ? FOR UPDATE", (cid,)
            ).fetchone()
            rows = db.execute(
                "SELECT * FROM course_modules WHERE course_id = ? ORDER BY module_number FOR UPDATE",
                (cid,),
            ).fetchall()
            metadata = copy.deepcopy(course["metadata_json"])
            canonical = {}
            for image in [
                *metadata.get("images", []),
                *[im for row in rows for im in row["metadata_json"].get("images", [])],
            ]:
                if image.get("file_path") or not image.get("image_id"):
                    continue
                filename = f"builder_{cid}_{image['image_id']}.png"
                path = (settings.image_dir / filename).resolve()
                if not path.is_relative_to(settings.image_dir.resolve()) or not path.is_file():
                    raise ValueError("Expected owned image is unavailable: " + filename)
                with Image.open(path) as opened:
                    opened.verify()
                canonical[image["image_id"]] = public_asset_url("images", filename)
            if not canonical:
                continue
            active = db.execute(
                "SELECT 1 FROM course_generation_status WHERE course_id = ? AND status = 'running'",
                (cid,),
            ).fetchone()
            if active:
                raise RuntimeError("Generation is active for " + cid)

            def normalize(value):
                if isinstance(value, dict):
                    if value.get("image_id") in canonical and not value.get("file_path"):
                        value["file_path"] = canonical[value["image_id"]]
                    for child in value.values():
                        normalize(child)
                elif isinstance(value, list):
                    for child in value:
                        normalize(child)

            normalize(metadata)
            updates = []
            for row in rows:
                changed = [
                    copy.deepcopy(row[key])
                    for key in ("metadata_json", "slides_json", "planned_slides_json")
                ]
                for value in changed:
                    normalize(value)
                if any(
                    value != row[key]
                    for value, key in zip(
                        changed, ("metadata_json", "slides_json", "planned_slides_json")
                    )
                ):
                    updates.append((row, changed))
            if apply:
                backup.mkdir(parents=True, exist_ok=True, mode=0o700)
                (backup / f"{cid}.json").write_text(
                    json.dumps(
                        {"course": dict(course), "modules": [dict(row) for row in rows]},
                        default=str,
                    ),
                    encoding="utf-8",
                )
                db.execute(
                    "UPDATE courses SET metadata_json = ? WHERE course_id = ?",
                    (Jsonb(metadata), cid),
                )
                for row, values in updates:
                    db.execute(
                        "UPDATE course_modules SET metadata_json = ?, slides_json = ?, planned_slides_json = ? WHERE course_id = ? AND module_number = ?",
                        (*[Jsonb(value) for value in values], cid, row["module_number"]),
                    )
                db.commit()
            affected = [row["module_number"] for row, _ in updates]
            results.append({"course_id": cid, "modules": affected, "images": len(canonical)})
        if apply:
            fresh = get_course(cid)
            assert fresh["status"] == course["status"]
            for row in rows:
                module = next(
                    m for m in fresh["modules"] if m["module_number"] == row["module_number"]
                )
                assert (
                    module["quiz"] == row["quiz_json"] and module["video_path"] == row["video_path"]
                )
            if render:
                from app.generation.html import generate_html_slides_for_module
                from app.generation.video import capture_slide_frames, render_video_for_module

                for number in affected:
                    module = next(m for m in fresh["modules"] if m["module_number"] == number)
                    if not module.get("slides"):
                        continue
                    media = backup / cid / f"module_{number}"
                    media.mkdir(parents=True, exist_ok=True)
                    if module.get("video_path"):
                        video = resolve_public_asset_path(module["video_path"], settings)
                        for old in video.parent.glob(video.stem + ".*"):
                            if old.is_file() and old.suffix != ".lock":
                                shutil.copy2(old, media / old.name)
                        hls = video.with_name(video.stem + "_hls")
                        if hls.is_dir():
                            shutil.copytree(hls, media / hls.name)
                    old_html = settings.slide_dir / cid / f"module_{number}.html"
                    if old_html.is_file():
                        shutil.copy2(old_html, media / old_html.name)
                    html = generate_html_slides_for_module(cid, number - 1, module)
                    frames = media / "verified-frames"
                    frames.mkdir()
                    capture_slide_frames(
                        html, slide_count=len(module["slides"]), output_dir=str(frames)
                    )
                    print(json.dumps({"verified_image_frames": cid, "module": number}), flush=True)
                    render_video_for_module(fresh, cid, number)
                    # Verify an image frame in the encoded MP4, not only the HTML.
                    import subprocess

                    import imageio_ffmpeg
                    from PIL import ImageChops, ImageStat

                    from app.generation.video import SLIDE_TRANSITION_PAUSE_SECONDS, audio_duration

                    elapsed = 0.0
                    for index, slide in enumerate(module["slides"]):
                        duration = audio_duration(
                            str(resolve_public_asset_path(slide["audio_path"], settings))
                        )
                        if slide.get("layout_type") == "image" or slide.get("is_image_slide"):
                            proof = frames / f"encoded-image-{index}.png"
                            video = resolve_public_asset_path(module["video_path"], settings)
                            subprocess.run(
                                [
                                    imageio_ffmpeg.get_ffmpeg_exe(),
                                    "-y",
                                    "-ss",
                                    str(elapsed + min(0.5, duration / 2)),
                                    "-i",
                                    str(video),
                                    "-frames:v",
                                    "1",
                                    str(proof),
                                ],
                                check=True,
                                capture_output=True,
                            )
                            with (
                                Image.open(frames / f"slide_{index}.png") as expected,
                                Image.open(proof) as actual,
                            ):
                                difference = ImageStat.Stat(
                                    ImageChops.difference(
                                        expected.convert("RGB"), actual.convert("RGB")
                                    )
                                ).mean
                            assert sum(difference) / 3 < 8, (
                                f"Encoded image frame differs from verified screenshot: {difference}"
                            )
                            print(
                                json.dumps(
                                    {
                                        "verified_encoded_image": cid,
                                        "module": number,
                                        "slide": index + 1,
                                        "mean_pixel_difference": sum(difference) / 3,
                                    }
                                ),
                                flush=True,
                            )
                        elapsed += duration + SLIDE_TRANSITION_PAUSE_SECONDS
                    print(json.dumps({"rebuilt_video": cid, "module": number}), flush=True)
    print(
        json.dumps(
            {"applied": apply, "results": results, "backup": str(backup) if apply else None}
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    repair_images(args.apply, args.render)
