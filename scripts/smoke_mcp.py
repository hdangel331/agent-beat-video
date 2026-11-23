"""Exercise the packaged WorkBuddy stdio configuration with the official MCP client."""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def smoke(root):
    repo = Path(__file__).resolve().parents[1]
    config = json.loads((repo / "integrations/workbuddy/mcp.json").read_text())[
        "mcpServers"
    ]["agent-beat-video"]
    args = config["args"].copy()
    args[args.index("--root") + 1] = str(root.resolve())
    env = dict(os.environ)
    server = StdioServerParameters(command=sys.executable, args=args, env=env)
    task = json.loads((repo / "examples/task.json").read_text(encoding="utf-8"))
    task.update(
        duration_s=10,
        resolution=720,
        fit="contain_blur",
        text_style="kinetic",
        random_seed=72,
    )
    async with (
        stdio_client(server) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        names = sorted(t.name for t in (await session.list_tools()).tools)

        async def call(name, args):
            reply = await session.call_tool(name, args)
            data = json.loads(reply.content[0].text)
            if reply.isError or data.get("error"):
                raise RuntimeError(str(data))
            return data

        scan = await call("scan_assets", {})
        a = await call("analyze_music", {"music_id": task["music_id"]})
        preview = await call("preview_edit_plan", {"task": task})
        job = await call(
            "create_video",
            {
                "plan_id": preview["plan_id"],
                "request_key": "smoke-" + preview["plan_id"],
            },
        )
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            state = await call("get_job_status", {"job_id": job["job_id"]})
            if state["status"] == "completed":
                break
            if state["status"] in ("failed", "cancelled"):
                raise RuntimeError(str(state))
            await asyncio.sleep(0.8)
        else:
            raise RuntimeError("Timed out")
        out = await call("get_video_result", {"job_id": job["job_id"]})
        assert Path(out["output_path"]).is_file() and out["qa_report"]["passed"]
        print(
            json.dumps(
                dict(
                    client="official MCP Python SDK / stdio",
                    tools=names,
                    assets=scan["asset_count"],
                    bpm=a["bpm"],
                    plan_id=preview["plan_id"],
                    job=job,
                    final=state,
                    qa=out["qa_report"],
                ),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    asyncio.run(smoke(p.parse_args().root))
