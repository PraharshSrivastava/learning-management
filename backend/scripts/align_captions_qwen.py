"""Optional isolated Qwen worker: request.json result.json. Uses local weights only.

A request holds either one slide ({"audio", "text", "language"} -> {"words"}) or a whole
module ({"items": [{"audio", "text"}], "language"} -> {"results": [{"words"}]}), so the
model loads once per module.
"""

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
    threads = os.environ.get("CAPTION_ALIGN_THREADS", "")
    if threads:
        import torch

        torch.set_num_threads(int(threads))
    from qwen_asr import Qwen3ForcedAligner

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    aligner = Qwen3ForcedAligner.from_pretrained(
        model, device_map=os.environ.get("CAPTION_ALIGN_DEVICE", "cpu")
    )

    def align(audio: str, text: str) -> list[dict]:
        results = aligner.align(audio=audio, text=text, language=request["language"])
        return [
            {"text": item.text, "start": item.start_time, "end": item.end_time}
            for item in results[0]
        ]

    if "items" in request:
        output = {"results": [{"words": align(i["audio"], i["text"])} for i in request["items"]]}
    else:
        output = {"words": align(request["audio"], request["text"])}
    Path(sys.argv[2]).write_text(json.dumps(output, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
