"""Run a real OpenCode v1 MCP tool call with a deterministic local test model."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent_beat_video import jobs
from agent_beat_video.model import Task
from agent_beat_video.planner import build
from agent_beat_video.store import Store


def smoke(executable, root):
    store = Store(root)
    task = Task(
        music_id="tide.wav",
        duration_s=10,
        resolution=720,
        text_blocks=[{"text": "山海有时", "role": "title"}],
        random_seed=73,
    )
    plan_id, _ = build(store, task, {})
    request_key = "opencode-test-" + plan_id
    calls = []

    class LocalModel(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            tool = next(
                (
                    t["function"]["name"]
                    for t in body.get("tools", [])
                    if t["function"]["name"].endswith("create_video")
                ),
                None,
            )
            already = tool is None or any(m["role"] == "tool" for m in body["messages"])
            delta = (
                {"role": "assistant", "content": "Test completed."}
                if already
                else {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_beat",
                            "type": "function",
                            "function": {
                                "name": tool,
                                "arguments": json.dumps(
                                    dict(plan_id=plan_id, request_key=request_key)
                                ),
                            },
                        }
                    ],
                }
            )
            if tool:
                calls.append("stop" if already else tool)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for d, finish in [(delta, None), ({}, "stop" if already else "tool_calls")]:
                chunk = {
                    "id": "fixture",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "fixture",
                    "choices": [{"index": 0, "delta": d, "finish_reason": finish}],
                }
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")

    with (
        tempfile.TemporaryDirectory() as directory,
        ThreadingHTTPServer(("127.0.0.1", 0), LocalModel) as server,
    ):
        threading.Thread(target=server.serve_forever, daemon=True).start()
        folder = Path(directory)
        cfg = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "localfixture": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Test fixture",
                    "options": {
                        "baseURL": f"http://127.0.0.1:{server.server_port}/v1",
                        "apiKey": "local-fixture",
                    },
                    "models": {"fixture": {"name": "Fixture"}},
                }
            },
            "model": "localfixture/fixture",
            "mcp": {
                "beatvideo": {
                    "type": "local",
                    "command": [
                        sys.executable,
                        "-m",
                        "agent_beat_video.cli",
                        "--root",
                        str(store.root),
                        "mcp",
                    ],
                    "timeout": 120000,
                }
            },
        }
        (folder / "opencode.json").write_text(json.dumps(cfg))
        env = os.environ | {
            "XDG_CONFIG_HOME": str(folder / "config"),
            "XDG_DATA_HOME": str(folder / "data"),
            "XDG_CACHE_HOME": str(folder / "cache"),
            "OPENCODE_CONFIG": str(folder / "opencode.json"),
            "PWD": str(folder),
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "OPENCODE_DISABLE_MODELS_FETCH": "1",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
        try:
            execution = subprocess.run(
                [
                    executable,
                    "--print-logs",
                    "run",
                    "--format",
                    "json",
                    "--model",
                    "localfixture/fixture",
                    "Run the local video test.",
                ],
                cwd=folder,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
        finally:
            server.shutdown()
        if execution.returncode or not calls or calls[-1] != "stop":
            raise RuntimeError(
                "OpenCode tool call failed: "
                + execution.stderr[-7000:]
                + execution.stdout[-1400:]
            )
        # The job must have been enqueued by OpenCode's MCP client during the tool call.
        with store.db() as db:
            row = db.execute(
                "SELECT id FROM jobs WHERE request_key=?", (request_key,)
            ).fetchone()
        if not row:
            raise RuntimeError("No job from the OpenCode tool call")
        for _ in range(300):
            state = jobs.status(store, row[0])
            if state["status"] == "completed":
                break
            if state["status"] in ("failed", "cancelled"):
                raise RuntimeError(str(state))
            time.sleep(1)
        result = jobs.result(store, row[0])
        print(
            json.dumps(
                dict(
                    client="OpenCode",
                    model="deterministic loopback test fixture",
                    calls=calls,
                    job_id=row[0],
                    frames=result["qa_report"]["frames"],
                    passed=result["qa_report"]["passed"],
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    smoke(str(args.executable.resolve()), args.root)
