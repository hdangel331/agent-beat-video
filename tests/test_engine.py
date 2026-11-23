import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from agent_beat_video import jobs
from agent_beat_video.model import Block, Task
from agent_beat_video.music import RATE, extract
from agent_beat_video.planner import build, cut_grid
from agent_beat_video.render import verify_plan
from agent_beat_video.store import Store, inside


def grid():
    return dict(
        asset_id="a" * 64,
        duration_s=24,
        confidence=0.92,
        beat_times=[x * 0.5 for x in range(48)],
        energy_sections=[{"start_s": 0, "level": "mid"}],
    )


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.s = Store(self.temp.name)
        for i in range(5):
            Image.new("RGB", (90, 128), (30 + i * 20, 155, 115)).save(
                self.s.assets / f"{i}.png"
            )
        self.s.scan()
        self.task = Task(music_id="demo.wav", text_blocks=[Block(text="山海有时")])

    def plan(self, seed=1):
        with patch("agent_beat_video.planner.analyze", return_value=grid()):
            return build(self.s, self.task.model_copy(update={"random_seed": seed}), {})

    def test_replay_and_three_variants(self):
        variants = [self.plan(i) for i in [1, 2, 3]]
        self.assertEqual(variants[0], self.plan(1))
        self.assertEqual(
            3, len({tuple(s.asset_id for s in p.shots) for _, p in variants})
        )
        for _, plan in variants:
            end = 0
            for shot in plan.shots:
                self.assertEqual(end, shot.start_frame)
                end += shot.duration_frames
            self.assertEqual(end, 600)
            self.assertTrue(
                all(
                    x.asset_id != y.asset_id for x, y in zip(plan.shots, plan.shots[1:])
                )
            )
            self.assertTrue(all(c.error_frames <= 0.5 for c in plan.cut_points))

    def test_manual_and_low_confidence(self):
        meta = grid() | {"confidence": 0.0}
        pts, w = cut_grid(self.task, meta, random.Random(2), 0, 600)
        self.assertTrue(w and pts and all(x["kind"] == "uniform" for x in pts))
        pts, w = cut_grid(
            self.task.model_copy(update={"manual_bpm": 120}),
            meta,
            random.Random(2),
            15,
            600,
        )
        self.assertTrue(
            pts and all(x["kind"] == "manual" and x["error_frames"] == 0 for x in pts)
        )

    def test_scan_dedup_missing_and_changed(self):
        (self.s.assets / "bad.jpg").write_bytes(b"bad image")
        scan = self.s.scan()
        self.assertEqual(scan["added"], 0)
        self.assertEqual(len(scan["warnings"]), 1)
        p = self.s.assets / "0.png"
        (self.s.assets / "duplicate.png").write_bytes(p.read_bytes())
        self.assertEqual(self.s.scan()["asset_count"], 5)
        p.unlink()
        self.assertEqual(len(self.s.pool(".")), 5)
        (self.s.assets / "duplicate.png").write_bytes(b"replaced")
        self.assertEqual(len(self.s.pool(".")), 4)

    def test_authorized_root(self):
        with self.assertRaises(ValueError):
            self.s.scan("../music")
        with self.assertRaises(ValueError):
            inside(self.s.music, "../assets/0.png")
        with self.assertRaises(ValueError):
            self.s.index("../assets/0.png", "music")

    def test_short_video_only_pool(self):
        clips = [
            dict(kind="video", asset_id="b" * 64, duration_s=1.25, height=160, width=90)
        ]
        with patch.object(self.s, "pool", return_value=clips):
            _, plan = self.plan()
        self.assertEqual(sum(shot.duration_frames for shot in plan.shots), 600)
        self.assertTrue(any(c.kind == "source_limit" for c in plan.cut_points))
        self.assertTrue(
            all(s.duration_frames + s.source_in_frames <= 37 for s in plan.shots)
        )

    def test_invalid_task_and_timeline(self):
        with self.assertRaises(ValueError):
            Block(text="{bad}")
        with self.assertRaises(ValueError):
            Task(music_id="a", duration_s=1)
        _, p = self.plan()
        p.shots[0].start_frame = 1
        with self.assertRaisesRegex(ValueError, "contiguous"):
            verify_plan(self.s, p)

    def test_job_dedup_cancel_and_reopen(self):
        key, _ = self.plan()
        with patch.object(jobs, "launch"):
            j = jobs.create(self.s, key, "one")
            self.assertEqual(j, jobs.create(self.s, key, "one"))
            self.assertEqual(jobs.cancel(self.s, j["job_id"])["status"], "cancelled")
            self.assertEqual(
                jobs.status(Store(self.temp.name), j["job_id"])["status"], "cancelled"
            )
            with self.assertRaises(ValueError):
                jobs.result(self.s, j["job_id"])


class AnnotatedMusicTests(unittest.TestCase):
    def test_offbeat_phase_reference(self):
        rng = np.random.default_rng(42)
        data = np.zeros(int(12 * RATE), np.float32)
        beats = np.arange(0.19, 11.8, 0.5)
        kick = rng.normal(0, 0.5, 1200) * np.exp(-np.arange(1200) / 170)
        for t in beats:
            start = round(t * RATE)
            data[start : start + len(kick)] += kick
        a = extract(data)
        self.assertAlmostEqual(a["bpm"], 120, delta=3)
        self.assertGreater(a["confidence"], 0.65)
        detected = np.array(a["beat_times"])
        self.assertGreaterEqual(
            np.mean([np.min(abs(detected - t)) <= 1 / 30 for t in beats[1:-1]]), 0.90
        )

    def test_silent_track(self):
        a = extract(np.zeros(10 * RATE, np.float32))
        self.assertLess(a["confidence"], 0.45)


if __name__ == "__main__":
    unittest.main()
