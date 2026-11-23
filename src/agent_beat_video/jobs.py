import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock, Timeout

from .planner import load_plan
from .render import render
from .store import encoded, inside


def now():
    return datetime.now(timezone.utc).isoformat()


def record(store, job_id):
    with store.db() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Unknown job_id")
    return dict(row)


def launch(store, job_id):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent_beat_video.cli",
            "--root",
            str(store.root),
            "_work",
            job_id,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


def wake(store, job_id):
    # A killed process releases its OS lock; status polling then starts recovery.
    stamp = inside(store.state, job_id + ".wake")
    with FileLock(str(stamp) + ".lock"):
        if stamp.exists() and time.time() - stamp.stat().st_mtime < 4:
            return
        lock = FileLock(str(inside(store.state, job_id + ".lock")))
        try:
            with lock.acquire(timeout=0):
                pass
        except Timeout:
            return
        stamp.touch()
        launch(store, job_id)


def create(store, plan_id, request_key=None):
    load_plan(store, plan_id)
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT id,plan,status FROM jobs WHERE request_key=?", (request_key,)
        ).fetchone()
        if row and row["plan"] != plan_id:
            raise ValueError("request_key already belongs to a different plan")
        if row:
            job_id = row["id"]
            status = row["status"]
        else:
            job_id = uuid.uuid4().hex
            status = "queued"
            db.execute(
                "INSERT INTO jobs VALUES(?,?,?, 'queued',0,NULL,NULL,?,?)",
                (job_id, plan_id, status, now(), request_key),
            )
    if status in ("queued", "running"):
        wake(store, job_id)
    return dict(job_id=job_id, status=status)


def status(store, job_id):
    row = record(store, job_id)
    if row["status"] in ("queued", "running"):
        wake(store, job_id)
    return dict(
        job_id=job_id, **{k: row[k] for k in ("status", "stage", "progress", "error")}
    )


def result(store, job_id):
    row = record(store, job_id)
    if row["status"] != "completed":
        raise ValueError("Result unavailable: " + row["status"])
    return dict(job_id=job_id, **json.loads(row["result"]))


def cancel(store, job_id):
    record(store, job_id)
    with store.db() as db:
        db.execute(
            "UPDATE jobs SET status='cancelled',stage='cancelled' WHERE id=? AND status IN ('queued','running')",
            (job_id,),
        )
    return status(store, job_id)


def retry(store, job_id):
    row = record(store, job_id)
    if row["status"] != "failed":
        raise ValueError("Only failed jobs can be retried")
    with store.db() as db:
        db.execute(
            "UPDATE jobs SET status='queued',stage='queued',error=NULL,progress=0 WHERE id=? AND status='failed'",
            (job_id,),
        )
    wake(store, job_id)
    return status(store, job_id)


def work(store, job_id):
    row = record(store, job_id)
    try:
        with FileLock(str(inside(store.state, job_id + ".lock")), timeout=0):
            execute(store, job_id, row)
    except Timeout:
        return


def execute(store, job_id, row):
    folder = inside(store.output, Path(row["created"][:10]) / job_id)

    def progress(stage, percent):
        with store.db() as db:
            changed = db.execute(
                "UPDATE jobs SET status='running',stage=?,progress=? WHERE id=? AND status IN ('queued','running')",
                (stage, percent, job_id),
            )
            if not changed.rowcount:
                raise InterruptedError("Job ended")

    try:
        if record(store, job_id)["status"] not in ("queued", "running"):
            return
        # Serialize encoding on one workstation and permit queued cancellation.
        global_lock = FileLock(str(inside(store.state, "encode.lock")))
        while True:
            try:
                global_lock.acquire(timeout=1)
                break
            except Timeout:
                if (
                    record(store, job_id)["status"] != "queued"
                    and record(store, job_id)["status"] != "running"
                ):
                    return
        try:
            progress("prepare", 1)
            if folder.exists():
                for path in folder.glob("render-*"):
                    if path.is_dir():
                        shutil.rmtree(path)
            plan = load_plan(store, row["plan"])
            rendered = render(store, plan, folder, progress)
            with store.db() as db:
                changed = db.execute(
                    "UPDATE jobs SET status='completed',stage='completed',progress=100,error=NULL,result=? WHERE id=? AND status='running'",
                    (encoded(rendered), job_id),
                )
                if not changed.rowcount:
                    raise InterruptedError("Cancelled before publish")
                counts = Counter(s.asset_id for s in plan.shots)
                db.executemany(
                    "INSERT OR REPLACE INTO usage VALUES(?,?,?,?)",
                    [(job_id, key, now(), count) for key, count in counts.items()],
                )
        finally:
            global_lock.release()
    except InterruptedError:
        if folder.exists():
            shutil.rmtree(folder)
    except Exception as e:
        with store.db() as db:
            db.execute(
                "UPDATE jobs SET status='failed',stage='failed',error=? WHERE id=? AND status IN ('queued','running')",
                (str(e)[-2000:], job_id),
            )
