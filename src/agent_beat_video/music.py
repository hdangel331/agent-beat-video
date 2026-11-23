import json
import re

import librosa
import numpy as np

from .store import encoded, media_input, run

RATE = 22050
HOP = 220
VERSION = f"grid-3/librosa-{librosa.__version__}"


def extract(samples):
    duration = len(samples) / RATE
    env = librosa.onset.onset_strength(y=samples, sr=RATE, hop_length=HOP)
    frames = librosa.onset.onset_detect(onset_envelope=env, sr=RATE, hop_length=HOP)
    _, beats = librosa.beat.beat_track(
        onset_envelope=env, sr=RATE, hop_length=HOP, trim=False
    )
    # Compensate one analysis hop for attack latency.
    delay = HOP / RATE
    to_seconds = lambda fs: np.maximum(0, np.asarray(fs) * HOP / RATE - delay)
    onsets = to_seconds(frames)
    beat_times = to_seconds(beats)
    beat_times = beat_times[beat_times < duration]
    gaps = np.diff(beat_times)
    bpm = float(60 / np.median(gaps)) if gaps.size else None
    regularity = 0.0
    support = 0.0
    if gaps.size >= 4 and len(onsets) >= 4:
        regularity = float(
            np.mean(abs(gaps - np.median(gaps)) < 0.12 * np.median(gaps))
        )
        support = float(np.mean([np.min(abs(onsets - b)) <= 0.075 for b in beat_times]))
    confidence = round(regularity * support, 3)
    rms = [
        float(np.sqrt(np.mean(x * x)))
        for x in np.array_split(samples, max(1, int(np.ceil(duration / 0.5))))
        if len(x)
    ]
    lo, hi = np.percentile(rms, [28, 72])
    sections = []
    for i, value in enumerate(rms):
        label = (
            "mid"
            if hi - lo < 0.002
            else ("low" if value <= lo else "high" if value >= hi else "mid")
        )
        t = round(i * duration / len(rms), 4)
        if not sections or sections[-1]["level"] != label:
            sections.append(dict(start_s=t, level=label))
    return dict(
        duration_s=duration,
        sample_rate=RATE,
        bpm=round(bpm, 2) if bpm else None,
        bpm_candidates=[round(bpm * f, 2) for f in (0.5, 1, 2)] if bpm else [],
        beat_times=np.round(beat_times, 5).tolist(),
        onsets=np.round(onsets, 5).tolist(),
        energy_rms=rms,
        energy_step_s=duration / len(rms),
        energy_sections=sections,
        confidence=confidence,
        confidence_type="heuristic",
        analyzer=VERSION,
    )


def analyze(store, music_id):
    if re.fullmatch(r"[0-9a-f]{64}", music_id):
        path, info = store.resolve(music_id, "music")
    else:
        info, _ = store.index(music_id, "music")
        path = store.music / info["path"]
    cache_key = VERSION + ":" + info["asset_id"]
    with store.db() as db:
        row = db.execute(
            "SELECT data FROM analyses WHERE id=?", (cache_key,)
        ).fetchone()
        if row:
            return json.loads(row[0])
    if info["duration_s"] > 1800:
        raise ValueError("Maximum source track length is 30 minutes.")
    raw = run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            *media_input(path),
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            str(RATE),
            "-f",
            "f32le",
            "-",
        ]
    )
    samples = np.frombuffer(raw, dtype="<f4")
    if len(samples) < RATE:
        raise ValueError("Music has less than one second of decoded audio")
    result = extract(samples)
    result.update(
        asset_id=info["asset_id"],
        source_sample_rate=int(info["sample_rate"]),
        suggested_range_s=[0, min(30, result["duration_s"])],
    )
    with store.db() as db:
        db.execute(
            "INSERT OR REPLACE INTO analyses VALUES(?,?)", (cache_key, encoded(result))
        )
    return result
