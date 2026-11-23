import hashlib
import math
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

from .model import Plan, Task
from .music import analyze
from .store import encoded


def cut_grid(task, a, rng, offset, total):
    fps = task.fps
    start = offset / fps
    end = (offset + total) / fps
    mode = "detected"
    confidence = a["confidence"]
    beats = a["beat_times"]
    if task.manual_bpm:
        mode = "manual"
        interval = 60 / task.manual_bpm
        beats = [i * interval for i in range(math.ceil(end / interval) + 1)]
    elif confidence < 0.45 or len(beats) < 3:
        step = round({"low": 3.5, "medium": 2.5, "high": 1.6}[task.cut_density] * fps)
        return [
            dict(frame=f, kind="uniform", candidate_s=None, error_frames=None)
            for f in range(step, total - fps // 2, step)
        ], ["未完成自动踩点，采用均匀切镜。"]
    beats = [b for b in beats if start <= b < end]
    if not beats:
        return [], ["选定音乐区段没有可用拍点。"]
    points = []
    idx = 0
    last = 0
    while idx < len(beats):
        stamp = beats[idx]
        energy = next(
            s["level"] for s in reversed(a["energy_sections"]) if s["start_s"] <= stamp
        )
        base = {"low": 8, "medium": 4, "high": 2}[task.cut_density]
        if energy == "high":
            base = max(2, base // 2)
        if energy == "low":
            base = min(8, base * 2)
        if mode == "detected" and confidence < 0.65:
            base = max(base, 4)
        if rng.random() < 0.30 * task.variation_strength:
            base = rng.choice([max(2, base // 2), base])
        idx += base
        if idx >= len(beats):
            break
        absolute = beats[idx]
        frame = round(absolute * fps) - offset
        if frame - last < math.ceil(0.65 * fps):
            continue
        if total - frame < math.ceil(0.65 * fps):
            break
        points.append(
            dict(
                frame=frame,
                kind=mode,
                candidate_s=absolute,
                error_frames=round(abs(frame + offset - absolute * fps), 5),
            )
        )
        last = frame
    warnings = [] if mode == "detected" else ["使用手动 BPM，以音频起点为网格原点。"]
    return points, warnings


def history(store, days):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store.db() as db:
        return {
            row[0]: row[1]
            for row in db.execute(
                "SELECT asset,SUM(count) FROM usage WHERE used>=? GROUP BY asset",
                (cutoff,),
            )
        }


def save_plan(store, plan):
    body = encoded(plan.model_dump())
    key = hashlib.sha256(body.encode()).hexdigest()
    with store.db() as db:
        db.execute("INSERT OR IGNORE INTO plans VALUES(?,?)", (key, body))
    return key


def load_plan(store, key):
    with store.db() as db:
        row = db.execute("SELECT data FROM plans WHERE id=?", (key,)).fetchone()
    if not row:
        raise ValueError("Unknown plan_id")
    return Plan.model_validate_json(row[0])


def build(store, task: Task, snapshot=None):
    assets = store.pool(task.asset_pool)
    if not assets:
        raise ValueError("No indexed assets. Scan the asset pool first.")
    caption = (
        task.caption or "\n".join(block.text for block in task.text_blocks) or None
    )
    if caption and any(term in caption for term in task.forbidden_terms if term):
        raise ValueError("Text contains a forbidden term")
    a = analyze(store, task.music_id)
    fps = task.fps
    total = round(task.duration_s * fps)
    offset = round(task.music_offset_s * fps)
    if (offset + total) / fps > a["duration_s"] + 0.0001:
        raise ValueError("Requested interval extends beyond available music")
    rng = random.Random(task.random_seed)
    points, warnings = cut_grid(task, a, rng, offset, total)
    hist = history(store, task.rotation_window_days) if snapshot is None else snapshot
    boundaries = [0, *[p["frame"] for p in points], total]
    if all(asset["kind"] != "image" for asset in assets):
        longest = max(math.floor(asset["duration_s"] * fps + 1e-6) for asset in assets)
        if longest < math.ceil(0.65 * fps):
            raise ValueError(
                "All clips are shorter than the minimum shot duration. Add one longer clip or still."
            )
        extra = []
        # Leave room to vary the source in-point when only one clip is available.
        capacity = longest - 1 if len(assets) == 1 else longest
        for left, right in zip(boundaries, boundaries[1:]):
            pieces = math.ceil((right - left) / capacity)
            extra.extend(
                left + round(i * (right - left) / pieces) for i in range(1, pieces)
            )
        if extra:
            warnings.append("按可用视频时长增加切点，附加切点单独标记。")
            points += [
                dict(frame=f, kind="source_limit", candidate_s=None, error_frames=None)
                for f in extra
            ]
            points.sort(key=lambda cut: cut["frame"])
            boundaries = sorted([*boundaries, *extra])
    counts = Counter()
    shots = []
    for left, right in zip(boundaries, boundaries[1:]):
        n = right - left
        candidates = [
            x
            for x in assets
            if x["kind"] == "image" or math.floor(x["duration_s"] * fps + 1e-6) >= n
        ]
        if not candidates:
            raise ValueError(
                f"No input covers a {n / fps:.2f}s shot. Add a still or longer clip."
            )
        prev = shots[-1] if shots else {}
        others = [a for a in candidates if a["asset_id"] != prev.get("asset_id")]
        if others:
            candidates = others
        weights = []
        for x in candidates:
            portrait_bonus = 1.18 if x["height"] > x["width"] else 1
            weights.append(
                portrait_bonus
                / (
                    (1 + hist.get(x["asset_id"], 0))
                    * (1 + counts[x["asset_id"]] * 4) ** 2
                )
            )
        item = rng.choices(candidates, weights=weights, k=1)[0]
        key = item["asset_id"]
        counts[key] += 1
        in_frame = 0
        motion = rng.choice(["in", "out"])
        if item["kind"] != "image":
            limit = math.floor(item["duration_s"] * fps + 1e-6) - n
            in_frame = rng.randint(0, limit)
        if key == prev.get("asset_id"):
            if item["kind"] == "image":
                motion = "out" if prev["motion"] == "in" else "in"
            elif in_frame == prev["source_in_frames"] and limit:
                in_frame = (in_frame + 1) % (limit + 1)
            warnings.append("素材有限，相邻镜头复用同一源文件。")
        shots.append(
            dict(
                asset_id=key,
                start_frame=left,
                duration_frames=n,
                source_in_frames=in_frame,
                motion=motion,
            )
        )
    # Independent RNG keeps the same imagery and beats when only the transition preset changes.
    effects_rng = random.Random(f"transitions:{task.random_seed}")
    bag = []
    for shot in shots[1:]:
        style = task.transition_style
        if style == "mixed":
            if not bag:
                bag = [
                    "cut",
                    "cut",
                    "cut",
                    "fade",
                    "wipeleft",
                    "slideright",
                    "circleopen",
                ]
                effects_rng.shuffle(bag)
            style = bag.pop()
        frames = min(round(0.32 * fps), shot["duration_frames"] // 2)
        if style != "cut" and frames >= 2:
            shot.update(transition=style, transition_frames=frames)
    plan = Plan(
        schema_version="1.1",
        caption=caption,
        seed=task.random_seed,
        fps=fps,
        total_frames=total,
        resolution=task.resolution,
        fit=task.fit,
        music=dict(asset_id=a["asset_id"], offset_frames=offset),
        shots=shots,
        text_events=[],
        cut_points=points,
        history_snapshot=hist,
        warnings=list(dict.fromkeys(warnings)),
    )
    key = save_plan(store, plan)
    return key, plan
