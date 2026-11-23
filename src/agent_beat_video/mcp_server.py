"""Local-only MCP adapter. The agent may operate only on the configured workspace."""

from mcp.server.fastmcp import FastMCP

from . import jobs
from .model import Task
from .music import analyze
from .planner import build


def serve(store):
    app = FastMCP("AgentBeatVideo")

    def call(fn, *args):
        try:
            return fn(*args)
        except (OSError, ValueError) as e:
            return {"error": {"code": "ABV_ERROR", "message": str(e)}}

    @app.tool()
    def scan_assets(library_path: str = ".", recursive: bool = True) -> dict:
        """Index media under the configured assets folder."""
        return call(store.scan, library_path, recursive)

    @app.tool()
    def list_assets(asset_pool: str = ".", page: int = 1) -> dict:
        """List up to 50 indexed stills/clips per page."""

        def listing():
            if page < 1:
                raise ValueError("Page must be positive")
            pool = store.pool(asset_pool)
            return dict(
                assets=pool[(page - 1) * 50 : page * 50],
                next_page=page + 1 if len(pool) > 50 * page else None,
            )

        return call(listing)

    @app.tool()
    def analyze_music(music_id: str) -> dict:
        """Analyze an indexed music hash or a filename inside the music folder."""
        return call(analyze, store, music_id)

    @app.tool()
    def preview_edit_plan(task: Task) -> dict:
        """Plan a seeded timeline. Scan assets first. Return the plan ID for rendering."""

        def preview():
            key, plan = build(store, task)
            return dict(
                plan_id=key,
                cut_points=[p.model_dump() for p in plan.cut_points],
                shot_count=len(plan.shots),
                warnings=plan.warnings,
            )

        return call(preview)

    @app.tool()
    def create_video(plan_id: str, request_key: str | None = None) -> dict:
        """Queue a previewed plan. Reuse request_key when retrying the same request."""
        return call(jobs.create, store, plan_id, request_key)

    @app.tool()
    def get_job_status(job_id: str) -> dict:
        """Return persistent job status, stage, progress and error."""
        return call(jobs.status, store, job_id)

    @app.tool()
    def get_video_result(job_id: str) -> dict:
        """Return the completed local MP4 path, manifest path and measured quality data."""
        return call(jobs.result, store, job_id)

    @app.tool()
    def cancel_job(job_id: str) -> dict:
        """Cancel a queued or running job at the next stage boundary."""
        return call(jobs.cancel, store, job_id)

    @app.tool()
    def retry_job(job_id: str) -> dict:
        """Retry a failed job without allocating another result directory."""
        return call(jobs.retry, store, job_id)

    app.run(transport="stdio")
