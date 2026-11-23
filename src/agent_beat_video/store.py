import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

IMAGES = {".jpg": "image2", ".jpeg": "image2", ".png": "image2", ".webp": "webp_pipe"}
VIDEOS = {".mp4": "mov", ".mov": "mov", ".m4v": "mov"}
AUDIO = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".flac": "flac",
    ".m4a": "mov",
    ".aac": "aac",
    ".ogg": "ogg",
}
FORMATS = {**IMAGES, **VIDEOS, **AUDIO}


def encoded(obj):
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, obj):
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
    os.replace(f.name, path)


def inside(folder, name):
    p = (folder / name).resolve()
    if not p.is_relative_to(folder):
        raise ValueError("Path is outside the authorized directory")
    return p


def media_input(path):
    fmt = FORMATS[path.suffix.lower()]
    opts = ["-protocol_whitelist", "file,pipe", "-f", fmt]
    if fmt == "image2":
        opts += ["-pattern_type", "none"]
    return opts


def run(args, **options):
    p = subprocess.run(args, capture_output=True, **options)
    if p.returncode:
        raise ValueError(p.stderr.decode("utf-8", "replace")[-1600:])
    return p.stdout


def probe(path):
    return json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                *media_input(path),
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )


class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for label in ("assets", "music", "state", "output"):
            folder = inside(self.root, label)
            folder.mkdir(exist_ok=True)
            setattr(self, label, folder)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS media (path TEXT, kind TEXT, id TEXT, info TEXT, PRIMARY KEY(kind,path));
                CREATE INDEX IF NOT EXISTS media_id ON media(id);
                CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, data TEXT);
                CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, data TEXT);
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, plan TEXT, status TEXT, stage TEXT, progress INTEGER,
                    error TEXT, result TEXT, created TEXT, request_key TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS usage (job TEXT, asset TEXT, used TEXT, count INTEGER, PRIMARY KEY(job,asset));
            """)

    @contextmanager
    def db(self):
        with closing(
            sqlite3.connect(inside(self.state, "engine.sqlite"), timeout=30)
        ) as db:
            db.row_factory = sqlite3.Row
            with db:
                yield db

    def index(self, path, kind):
        path = inside(self.music if kind == "music" else self.assets, path)
        if not path.is_file():
            raise ValueError("Missing input file")
        allowed = AUDIO if kind == "music" else IMAGES | VIDEOS
        if path.suffix.lower() not in allowed:
            raise ValueError("Unsupported media format")
        key = digest(path)
        relative = path.relative_to(
            self.music if kind == "music" else self.assets
        ).as_posix()
        with self.db() as db:
            old = db.execute(
                "SELECT info FROM media WHERE kind=? AND path=? AND id=?",
                (kind, relative, key),
            ).fetchone()
            if old:
                return json.loads(old[0]), False
        p = probe(path)
        expected = "audio" if kind == "music" else "video"
        stream = next((s for s in p["streams"] if s["codec_type"] == expected), None)
        if stream is None:
            raise ValueError(f"Missing {expected} stream")
        run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-xerror",
                *media_input(path),
                "-i",
                str(path),
                "-map",
                f"0:{stream['index']}",
                "-frames:" + expected[0],
                "1",
                "-f",
                "null",
                "-",
            ]
        )
        mtype = "image" if path.suffix.lower() in IMAGES else kind
        duration = float(stream.get("duration") or p["format"].get("duration") or 0)
        if mtype != "image" and duration <= 0:
            raise ValueError("Missing media duration")
        info = dict(
            asset_id=key,
            path=relative,
            kind=mtype,
            width=stream.get("width"),
            height=stream.get("height"),
            duration_s=duration,
            fps=stream.get("avg_frame_rate"),
            sample_rate=stream.get("sample_rate"),
        )
        with self.db() as db:
            db.execute(
                "INSERT OR REPLACE INTO media VALUES(?,?,?,?)",
                (relative, kind, key, encoded(info)),
            )
        return info, True

    def scan(self, library_path=".", recursive=True):
        folder = inside(self.assets, library_path)
        if not folder.is_dir():
            raise ValueError("Asset pool directory does not exist")
        added = 0
        warnings = []
        valid = []
        paths = folder.rglob("*") if recursive else folder.glob("*")
        for p in sorted(paths):
            if p.is_file() and p.suffix.lower() in IMAGES | VIDEOS:
                try:
                    info, new = self.index(p, "video")
                    added += new
                    valid.append(info["asset_id"])
                except (ValueError, OSError) as e:
                    warnings.append(f"{p.name}: {e}")
        return dict(asset_count=len(set(valid)), added=added, warnings=warnings)

    def pool(self, name):
        directory = inside(self.assets, name)
        if not directory.is_dir():
            raise ValueError("Unknown asset pool")
        result = {}
        with self.db() as db:
            for row in db.execute(
                "SELECT info FROM media WHERE kind='video' ORDER BY path"
            ):
                item = json.loads(row[0])
                try:
                    path = inside(self.assets, item["path"])
                except ValueError:
                    continue
                if (
                    path.is_relative_to(directory)
                    and path.is_file()
                    and digest(path) == item["asset_id"]
                ):
                    result[item["asset_id"]] = item
        return sorted(result.values(), key=lambda a: a["asset_id"])

    def resolve(self, key, kind):
        folder = self.music if kind == "music" else self.assets
        with self.db() as db:
            rows = db.execute(
                "SELECT info FROM media WHERE id=? AND kind=? ORDER BY path",
                (key, kind),
            ).fetchall()
        for row in rows:
            info = json.loads(row[0])
            path = inside(folder, info["path"])
            if path.is_file() and digest(path) == key:
                return path, info
        raise ValueError("Referenced asset is missing or has changed: " + key[:12])
