"""Compare decoded frames against the planned caption's fixed glyph positions."""

import subprocess

import numpy as np
from PIL import Image


def measure_caption(video, tile_path, layout):
    with Image.open(tile_path) as tile:
        rgba = np.array(tile)
    h, w = rgba.shape[:2]
    opaque = rgba[:, :, 3] == 255
    ink = opaque & (rgba[:, :, 0] >= 245)
    outline = opaque & (rgba[:, :, 0] <= 40)
    if not ink.any() or not outline.any():
        raise ValueError("Caption has no measurable solid ink/outline")
    crop = f"format=gray,crop={w}:{h}:{layout['x']}:{layout['y']}:exact=1"
    args = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(video),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        crop,
        "-fps_mode",
        "passthrough",
        "-f",
        "rawvideo",
        "-",
    ]
    count = 0
    worst = 1.0
    bad = []
    with subprocess.Popen(args, stdout=subprocess.PIPE) as decoder:
        while block := decoder.stdout.read(h * w):
            if len(block) != h * w:
                raise ValueError("Incomplete decoded frame")
            frame = np.frombuffer(block, np.uint8).reshape(h, w)
            score = min(
                float((frame[ink] > 194).mean()), float((frame[outline] < 95).mean())
            )
            worst = min(worst, score)
            if score < 0.97:
                bad.append(count)
            count += 1
        if decoder.wait():
            raise RuntimeError("Decode failed")
    return {
        "passed": not bad and count == layout["duration_frames"],
        "frames_checked": count,
        "min_matching_fraction": round(worst, 6),
        "failed_frames": bad,
        "caption": layout["text"],
        "box_xyxy": layout["safe_box"],
    }
