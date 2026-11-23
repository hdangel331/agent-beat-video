import math
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from .music import analyze
from .store import digest, media_input, probe, run, write_json
from .typography import subtitles


def verify_plan(store, plan):
    if not 10 <= plan.total_frames / plan.fps <= 60:
        raise ValueError("Invalid target duration")
    offset = 0
    sources = {}
    for shot in plan.shots:
        if shot.start_frame != offset:
            raise ValueError("Shots must be contiguous from frame zero")
        offset += shot.duration_frames
        if shot.asset_id not in sources:
            sources[shot.asset_id] = store.resolve(shot.asset_id, "video")
        _, info = sources[shot.asset_id]
        if info["kind"] == "image" and shot.source_in_frames:
            raise ValueError("Stills require source_in_frames=0")
        if info[
            "kind"
        ] != "image" and shot.source_in_frames + shot.duration_frames > math.floor(
            info["duration_s"] * plan.fps + 1e-6
        ):
            raise ValueError("Shot exceeds source duration")
    if offset != plan.total_frames:
        raise ValueError("Shots do not cover the target frame count")
    for e in plan.text_events:
        if e.start_frame + e.duration_frames > offset:
            raise ValueError("Text exceeds timeline")
    music, info = store.resolve(plan.music.asset_id, "music")
    if (plan.music.offset_frames + offset) / plan.fps > info["duration_s"] + 0.001:
        raise ValueError("Music interval exceeds source duration")
    return sources, music


def shot_filter(plan, shot, still):
    w, h = plan.resolution, plan.resolution * 16 // 9
    cover = f"scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h}"
    if plan.fit == "contain_blur":
        fit = (
            f"split[base][subject];[base]{cover},gblur=sigma=22,eq=brightness=-0.08[bg];"
            f"[subject]scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        fit = cover
    if still:
        delta = f"0.065*on/{max(1, shot.duration_frames - 1)}"
        zoom = "1+" + delta if shot.motion == "in" else "1.065-" + delta
        fit += f",scale={w * 2}:-2,zoompan=z='{zoom}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={shot.duration_frames}:s={w}x{h}:fps={plan.fps}"
    else:
        fit += f",fps={plan.fps},tpad=stop_mode=clone:stop_duration={2 / plan.fps:.8f}"
    return fit + ",setsar=1,format=yuv420p"


def inspect_video(path, plan, analysis):
    p = probe(path)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next(s for s in p["streams"] if s["codec_type"] == "audio")
    # Full decode to small grayscale frames; each frame contributes to black/freeze checks.
    raw = run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-vf",
            "scale=72:128",
            "-fps_mode",
            "passthrough",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 128, 72)
    black = np.flatnonzero((frames <= 12).mean(axis=(1, 2)) >= 0.985).tolist()
    diffs = np.mean(np.abs(np.diff(frames.astype("int16"), axis=0)), axis=(1, 2))
    longest = current = 0
    for diff in diffs:
        current = current + 1 if diff < 0.02 else 0
        longest = max(longest, current)
    pcm = np.frombuffer(
        run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-xerror",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-f",
                "f32le",
                "-",
            ]
        ),
        dtype="<f4",
    )
    peak = float(np.max(np.abs(pcm))) if len(pcm) else 0
    errors = []
    if len(frames) != plan.total_frames:
        errors.append("frame_count")
    if (v["width"], v["height"]) != (plan.resolution, plan.resolution * 16 // 9):
        errors.append("size")
    if (v["codec_name"], a["codec_name"]) != ("h264", "aac"):
        errors.append("codecs")
    if abs(float(a["duration"]) - len(frames) / plan.fps) > 1 / plan.fps:
        errors.append("audio_duration")
    if black:
        errors.append("black_frames")
    if peak < 0.0001:
        errors.append("silent_audio")
    if peak >= 1:
        errors.append("audio_clipping")
    warnings = list(plan.warnings)
    if longest >= 2 * plan.fps:
        warnings.append("检测到至少两秒近似静止画面，建议查看原素材。")
    reference = analysis["beat_times"]
    boundaries = {s.start_frame for s in plan.shots[1:]}
    errors_on_grid = [
        min(abs(p.frame + plan.music.offset_frames - b * plan.fps) for b in reference)
        for p in plan.cut_points
        if p.kind == "detected" and p.frame in boundaries and reference
    ]
    sync_ratio = (
        sum(x <= 1 for x in errors_on_grid) / len(errors_on_grid)
        if errors_on_grid
        else None
    )
    if sync_ratio is not None and sync_ratio < 0.90:
        errors.append("cut_alignment")
    return dict(
        passed=not errors,
        errors=errors,
        warnings=warnings,
        frames=len(frames),
        width=v["width"],
        height=v["height"],
        fps=v["avg_frame_rate"],
        video_codec=v["codec_name"],
        audio_codec=a["codec_name"],
        duration_s=float(v["duration"]),
        audio_duration_s=float(a["duration"]),
        audio_peak=round(peak, 5),
        black_frames=black,
        longest_nearly_static_frames=longest,
        detected_cut_count=len(errors_on_grid),
        beat_sync_fraction_within_one_frame=sync_ratio,
    )


def render(store, plan, folder, progress):
    sources, music = verify_plan(store, plan)
    analysis = analyze(store, plan.music.asset_id)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "plan.json", plan.model_dump())
    write_json(folder / "analysis.json", analysis)
    with (
        TemporaryDirectory(dir=folder, prefix="render-") as tmp,
        (folder / "render.log").open("w", encoding="utf-8") as log,
    ):
        tmp = Path(tmp)
        layout = subtitles(plan, tmp) if plan.text_events else []

        def ff(args):
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "warning",
                    "-filter_complex_threads",
                    "2",
                    "-filter_threads",
                    "2",
                    *args,
                ],
                cwd=tmp,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
            )
            message = result.stderr.decode("utf-8", "replace")
            log.write(message)
            log.flush()
            if result.returncode:
                raise ValueError(message[-1300:])

        files = []
        for i, s in enumerate(plan.shots):
            progress("shots", 5 + int(65 * i / len(plan.shots)))
            path, info = sources[s.asset_id]
            still = info["kind"] == "image"
            seek = [] if still else ["-ss", f"{s.source_in_frames / plan.fps:.9f}"]
            name = f"shot{i:03d}.mp4"
            ff(
                [
                    *seek,
                    *media_input(path),
                    "-i",
                    str(path),
                    "-an",
                    "-vf",
                    shot_filter(plan, s, still),
                    "-frames:v",
                    str(s.duration_frames),
                    "-c:v",
                    "libx264",
                    "-threads",
                    "3",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "17",
                    "-video_track_timescale",
                    str(plan.fps * 1000),
                    name,
                ]
            )
            frames = int(probe(tmp / name)["streams"][0]["nb_frames"])
            if frames != s.duration_frames:
                raise ValueError(
                    f"Source decoded {frames} frames; shot requires {s.duration_frames}"
                )
            files.append("file '" + name + "'")
        progress("mux", 74)
        (tmp / "clips.txt").write_text("\n".join(files) + "\n", encoding="ascii")
        seconds = plan.total_frames / plan.fps
        video = (
            [
                "-vf",
                "ass=captions.ass:fontsdir=fonts",
                "-c:v",
                "libx264",
                "-threads",
                "4",
                "-preset",
                "veryfast",
                "-crf",
                "19",
            ]
            if layout
            else ["-c:v", "copy"]
        )
        ff(
            [
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                "clips.txt",
                "-ss",
                f"{plan.music.offset_frames / plan.fps:.9f}",
                *media_input(music),
                "-i",
                str(music),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                *video,
                "-af",
                f"aresample=48000,afade=t=in:d=0.04,afade=t=out:st={seconds - 0.28:.9f}:d=0.28",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-t",
                f"{seconds:.9f}",
                "-movflags",
                "+faststart",
                "video.mp4",
            ]
        )
        progress("quality", 90)
        qa = inspect_video(tmp / "video.mp4", plan, analysis)
        qa["text_layout"] = layout
        write_json(folder / "qa.json", qa)
        if not qa["passed"]:
            raise ValueError("Quality checks failed: " + ", ".join(qa["errors"]))
        progress("publish", 98)
        checksum = digest(tmp / "video.mp4")
        write_json(
            folder / "manifest.json",
            dict(
                schema_version="1.0",
                video="video.mp4",
                sha256=checksum,
                plan="plan.json",
                analysis="analysis.json",
                qa="qa.json",
                seed=plan.seed,
                shots=len(plan.shots),
                renderer="ffmpeg",
                assets=sorted(sources),
            ),
        )
        os.replace(tmp / "video.mp4", folder / "video.mp4")
    return dict(
        output_path=str(folder / "video.mp4"),
        manifest_path=str(folder / "manifest.json"),
        qa_report=qa,
    )
