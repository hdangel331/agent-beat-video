import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw
from test_engine import grid

from agent_beat_video.caption_quality import measure_caption
from agent_beat_video.model import Plan, Task
from agent_beat_video.planner import build
from agent_beat_video.render import encode_shot
from agent_beat_video.store import Store
from agent_beat_video.typography import fixed_caption, font_for


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.store = Store(cls.root)
        for name, color in [("one", "navy"), ("two", "maroon")]:
            frame = Image.new("RGB", (90, 160), color)
            ImageDraw.Draw(frame).rectangle((18, 0, 39, 159), fill="yellow")
            frame.save(cls.store.assets / (name + ".png"))
        cls.store.scan()

    def plan(self, **config):
        task = Task(music_id="test.wav", **config)
        with patch("agent_beat_video.planner.analyze", return_value=grid()):
            return build(self.store, task, {})[1]

    def test_default_static_caption_and_legacy_text(self):
        p = self.plan(caption="山海有时")
        self.assertEqual(
            (p.schema_version, p.caption, p.text_events), ("1.1", "山海有时", [])
        )
        flat = self.plan(
            text_blocks=[{"text": "第一次见海"}, {"text": "一直记得"}],
            text_style="kinetic",
        )
        self.assertEqual(flat.caption, "第一次见海\n一直记得")
        with self.assertRaises(ValueError):
            self.plan(caption="A", text_blocks=[{"text": "B"}])
        with self.assertRaises(ValueError):
            self.plan(caption="山海", forbidden_terms=["海"])

    def test_only_bundled_font_and_safe_layout(self):
        p = self.plan(caption="远山有风，海上有光。" * 5)
        with patch.dict("os.environ", {"ABV_FONT": "/not-an-allowed-font.ttf"}):
            layout = fixed_caption(p, self.root)
        self.assertEqual(layout["font_license"], "OFL-1.1")
        self.assertEqual(layout["duration_frames"], 600)
        self.assertGreater(layout["lines"], 1)
        self.assertTrue((self.root / "caption.png").is_file())
        self.assertEqual(Path(font_for()[0]).name, "NotoSansSC-Regular.otf")
        with self.assertRaisesRegex(ValueError, "glyph"):
            fixed_caption(self.plan(caption="图\U0010ffff"), self.root)

    def test_single_missing_caption_frame_is_reported(self):
        tile = np.full((16, 16, 4), 255, dtype=np.uint8)
        tile[:, :8, :3] = 0
        tile_path = self.root / "check-tile.png"
        Image.fromarray(tile).save(tile_path)
        frames = np.full((4, 64, 64, 3), 128, dtype=np.uint8)
        for i in (0, 1, 3):
            frames[i, 8:24, 8:24] = tile[:, :, :3]
        video = self.root / "missing-frame.mkv"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", "64x64", "-r", "30", "-i", "pipe:0", "-c:v", "ffv1", str(video),
            ],
            input=frames.tobytes(),
            check=True,
        )
        result = measure_caption(
            video, tile_path,
            {"x": 8, "y": 8, "safe_box": [8, 8, 24, 24], "text": "A", "duration_frames": 4},
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["frames_checked"], 4)
        self.assertEqual(result["failed_frames"], [2])

    def test_render_legacy_plan(self):
        path = Path(__file__).resolve().parents[1] / "examples/evidence/plan-71.json"
        legacy = Plan.model_validate_json(path.read_bytes())
        self.assertEqual(legacy.schema_version, "1.0")
        self.assertIsNone(legacy.caption)
        self.assertTrue(legacy.text_events)
        from agent_beat_video.typography import subtitles

        self.assertTrue(subtitles(legacy, self.root))

    def test_transition_seed_and_explicit_preset(self):
        p = self.plan(caption="山海")
        self.assertEqual(p, self.plan(caption="山海"))
        self.assertGreaterEqual(len({s.transition for s in p.shots[1:]}), 4)
        hard = self.plan(caption="山海", transition_style="cut")
        self.assertTrue(
            all(s.transition == "cut" and s.transition_frames == 0 for s in hard.shots)
        )
        self.assertEqual(
            [s.asset_id for s in p.shots], [s.asset_id for s in hard.shots]
        )
        self.assertEqual(p.cut_points, hard.cut_points)

    def test_all_transitions_produce_different_pixels(self):
        # Encode the same two moving patterned shots five ways; compare the decoded midpoint.
        p = self.plan(caption="恒定", transition_style="cut")
        p.shots = p.shots[:2]
        p.shots[0].duration_frames = 12
        p.shots[1].start_frame = 12
        p.shots[1].duration_frames = 12
        shots = self.store.pool(".")
        dest = self.root / "transition-samples"
        dest.mkdir()

        def ff(args):
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-filter_complex_threads",
                    "2",
                    *args,
                ],
                cwd=dest,
                check=True,
            )

        results = []
        for effect in ["cut", "fade", "wipeleft", "slideright", "circleopen"]:
            p.shots[1].transition = effect
            p.shots[1].transition_frames = 0 if effect == "cut" else 8
            for i, source in enumerate(shots):
                encode_shot(ff, p, i, self.store.assets / source["path"], source)
            raw = subprocess.check_output(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-i",
                    str(dest / "shot001.mp4"),
                    "-vf",
                    "scale=36:64",
                    "-pix_fmt",
                    "rgb24",
                    "-f",
                    "rawvideo",
                    "-",
                ]
            )
            frames = np.frombuffer(raw, np.uint8).reshape(-1, 64, 36, 3)
            self.assertEqual(len(frames), 12)
            results.append(frames[4].astype(float))
        for i, result in enumerate(results):
            for earlier in results[:i]:
                self.assertGreater(np.abs(result - earlier).mean(), 2)


if __name__ == "__main__":
    unittest.main()
