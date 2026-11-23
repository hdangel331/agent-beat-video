import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import jobs
from .model import Plan, Task
from .music import analyze
from .planner import build, save_plan
from .render import verify_plan
from .store import Store


def main():
    parser = argparse.ArgumentParser(
        prog="agent-beat-video", description="本地音乐卡点视频 CLI"
    )
    parser.add_argument(
        "--root",
        default=os.getenv("ABV_ROOT"),
        help="授权工作目录，包含 assets/、music/、state/、output/",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan")
    scan.add_argument("pool", nargs="?", default=".")
    ana = commands.add_parser("analyze")
    ana.add_argument("music_id")
    for name in ("plan", "make"):
        cmd = commands.add_parser(name)
        cmd.add_argument("task", type=Path)
        cmd.add_argument("--history-from", type=Path, help="复用已有计划里的历史快照")
    new = commands.add_parser("create")
    group = new.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan-id")
    group.add_argument("--plan-file", type=Path)
    new.add_argument("--request-key")
    for name in ("status", "result", "cancel", "retry", "_work"):
        commands.add_parser(name).add_argument("job_id")
    commands.add_parser("mcp")
    args = parser.parse_args()
    if not args.root:
        parser.error("Set --root or ABV_ROOT to the authorized workspace.")
    try:
        store = Store(args.root)
        cmd = args.command
        if cmd == "mcp":
            from .mcp_server import serve

            serve(store)
            return
        if cmd == "_work":
            jobs.work(store, args.job_id)
            return
        if cmd == "scan":
            output = store.scan(args.pool)
        elif cmd == "analyze":
            output = analyze(store, args.music_id)
        elif cmd in ("plan", "make"):
            task = Task.model_validate_json(args.task.read_text(encoding="utf-8-sig"))
            history = (
                None
                if args.history_from is None
                else Plan.model_validate_json(
                    args.history_from.read_text(encoding="utf-8-sig")
                ).history_snapshot
            )
            if cmd == "make":
                store.scan(task.asset_pool)
            key, plan = build(store, task, history)
            output = dict(plan_id=key, plan=plan.model_dump())
            if cmd == "make":
                job = jobs.create(store, key)
                print(f"job_id={job['job_id']}", file=sys.stderr, flush=True)
                while (state := jobs.status(store, job["job_id"]))["status"] in (
                    "queued",
                    "running",
                ):
                    time.sleep(0.5)
                if state["status"] != "completed":
                    raise ValueError(state["error"] or state["status"])
                output = jobs.result(store, job["job_id"])
        elif cmd == "create":
            key = args.plan_id
            if args.plan_file:
                plan = Plan.model_validate_json(
                    args.plan_file.read_text(encoding="utf-8-sig")
                )
                verify_plan(store, plan)
                from .model import CutPoint

                declared = {p.frame: p for p in plan.cut_points}
                plan.cut_points = [
                    declared.get(
                        s.start_frame, CutPoint(frame=s.start_frame, kind="edited")
                    )
                    for s in plan.shots[1:]
                ]
                key = save_plan(store, plan)
            output = jobs.create(store, key, args.request_key)
        else:
            output = {
                "status": jobs.status,
                "result": jobs.result,
                "retry": jobs.retry,
                "cancel": jobs.cancel,
            }[cmd](store, args.job_id)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ImportError) as error:
        print(
            json.dumps(
                {"error": {"code": "ABV_ERROR", "message": str(error)}},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
