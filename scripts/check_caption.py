"""Check the caption's opaque ink and outline at the same pixels of every decoded frame."""

import argparse
import json
import tempfile
from pathlib import Path

from agent_beat_video.caption_quality import measure_caption
from agent_beat_video.model import Plan
from agent_beat_video.typography import fixed_caption


def check(video, plan):
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        layout = fixed_caption(plan, folder)
        return measure_caption(video, folder / "caption.png", layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_folder", type=Path)
    root = parser.parse_args().job_folder
    result = check(
        root / "video.mp4", Plan.model_validate_json((root / "plan.json").read_bytes())
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
