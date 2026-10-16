"""Optional isolated Qwen worker: request.json result.json. Uses local weights only."""

import json
import os
import sys
from pathlib import Path


def main() -> None:
    model = os.environ.get("CAPTION_ALIGN_MODEL_PATH", "")
    if not model or not Path(model).is_dir():
        raise RuntimeError(
            "Set CAPTION_ALIGN_MODEL_PATH to validated local Qwen3-ForcedAligner weights"
        )
    # Keep the GPU/ML dependency stack outside the LMS API environment.
    os.environ["HF_HUB_OFFLINE"] = "1"
    from qwen_asr import Qwen3ForcedAligner

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    aligner = Qwen3ForcedAligner.from_pretrained(
        model, device_map=os.environ.get("CAPTION_ALIGN_DEVICE", "cpu")
    )
    results = aligner.align(
        audio=request["audio"], text=request["text"], language=request["language"]
    )
    words = [
        {"text": item.text, "start": item.start_time, "end": item.end_time} for item in results[0]
    ]
    Path(sys.argv[2]).write_text(json.dumps({"words": words}, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
