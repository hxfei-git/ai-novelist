"""FastAPI application for the local Web UI."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.adapters.deepseek import DeepSeekAdapter
from ai_novelist.config import Settings, load_settings
from ai_novelist.storage.local_store import LocalStore, LocalStoreError
from ai_novelist.web import service


def make_app(settings: Settings | None = None, *, mock: bool = False):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import StreamingResponse
        from fastapi.staticfiles import StaticFiles
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without web extra.
        raise RuntimeError("Install the web extra first: pip install -e '.[web]'") from exc

    settings = settings or load_settings()
    store = LocalStore(settings.projects_dir)
    app = FastAPI(title="AI Novelist Web")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def adapter(payload: dict[str, Any] | None = None):
        payload = payload or {}
        use_mock = bool(payload.get("mock", mock))
        timeout = payload.get("timeout")
        timeout_seconds = int(timeout) if isinstance(timeout, int) else settings.codex_timeout_seconds
        if use_mock:
            return CodexCLIAdapter(timeout_seconds=timeout_seconds, mock=True)
        provider = str(payload.get("provider") or settings.model_provider).strip().lower()
        if provider == "deepseek":
            return DeepSeekAdapter(
                api_key=settings.deepseek_api_key,
                model=str(payload.get("model") or settings.deepseek_model),
                base_url=settings.deepseek_base_url,
                timeout_seconds=timeout_seconds,
            )
        return CodexCLIAdapter(codex_bin=settings.codex_bin, timeout_seconds=timeout_seconds)

    def as_http_error(exc: Exception) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))

    def sse_events(run):
        from queue import Queue
        from threading import Thread

        queue: Queue[tuple[str, dict[str, Any]]] = Queue()

        def progress(stage: str, message: str) -> None:
            queue.put(("progress", {"stage": stage, "message": message}))

        def worker() -> None:
            try:
                queue.put(("done", run(progress)))
            except Exception as exc:
                queue.put(("error", {"error": str(exc)}))

        Thread(target=worker, daemon=True).start()
        while True:
            event, data = queue.get()
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            if event in {"done", "error"}:
                break

    @app.get("/api/projects")
    def projects():
        return [item.__dict__ for item in service.list_projects(store)]

    @app.post("/api/projects")
    def create_project(payload: dict[str, Any]):
        try:
            state = service.create_project(store, str(payload.get("title") or ""), payload.get("project_id"), str(payload.get("idea") or ""))
            return state.to_dict()
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.get("/api/projects/{project_id}/state")
    def project_state(project_id: str):
        try:
            return store.load_state(project_id).to_dict()
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.get("/api/projects/{project_id}/outline/stages")
    def outline_stages(project_id: str):
        try:
            return service.outline_stage_list(store, project_id)
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.get("/api/projects/{project_id}/outline/stages/{stage}")
    def outline_stage(project_id: str, stage: str):
        try:
            return service.load_outline_stage_payload(store, project_id, stage)
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.put("/api/projects/{project_id}/outline/stages/{stage}")
    def save_outline_stage(project_id: str, stage: str, payload: dict[str, Any]):
        try:
            return service.save_outline_stage_content(store, project_id, stage, str(payload.get("content") or ""))
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.post("/api/projects/{project_id}/outline/stages/{stage}/generate")
    def generate_outline_stage(project_id: str, stage: str, payload: dict[str, Any] | None = None):
        payload = payload or {}
        return StreamingResponse(
            sse_events(lambda progress: service.generate_outline_stage(store, adapter(payload), project_id, stage, str(payload.get("instruction") or ""), progress).to_dict()),
            media_type="text/event-stream",
        )

    @app.post("/api/projects/{project_id}/outline/stages/{stage}/lock")
    def lock_outline_stage(project_id: str, stage: str, payload: dict[str, Any] | None = None):
        payload = payload or {}
        return StreamingResponse(
            sse_events(lambda progress: service.lock_outline_stage(store, adapter(payload), project_id, stage, str(payload.get("instruction") or ""), progress).to_dict()),
            media_type="text/event-stream",
        )

    @app.get("/api/projects/{project_id}/chapters")
    def chapters(project_id: str):
        try:
            return service.list_chapters(store, project_id)
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.get("/api/projects/{project_id}/chapters/{chapter}")
    def chapter_detail(project_id: str, chapter: int):
        try:
            return service.load_chapter_payload(store, project_id, chapter)
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.post("/api/projects/{project_id}/chapters/generate-batch")
    def generate_chapter_batch(project_id: str, payload: dict[str, Any]):
        return StreamingResponse(
            sse_events(
                lambda progress: service.generate_chapter_batch(
                    store,
                    adapter(payload),
                    project_id,
                    volume=int(payload.get("volume") or 1),
                    chapters=payload.get("chapters"),
                    max_workers=int(payload.get("max_workers") or 3),
                    progress=progress,
                ).to_dict()
            ),
            media_type="text/event-stream",
        )

    @app.post("/api/projects/{project_id}/chapters/review-all")
    def review_all(project_id: str, payload: dict[str, Any] | None = None):
        payload = payload or {}
        return StreamingResponse(
            sse_events(lambda progress: service.review_all_chapters(store, adapter(payload), project_id, progress)),
            media_type="text/event-stream",
        )

    @app.get("/api/projects/{project_id}/chapters/review-all/latest")
    def latest_review(project_id: str):
        try:
            return service.latest_global_review(store, project_id)
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.post("/api/projects/{project_id}/chapters/review-all/{run_id}/repair-proposals")
    def repair_proposals(project_id: str, run_id: str, payload: dict[str, Any] | None = None):
        try:
            return service.generate_repair_proposals(store, adapter(payload), project_id, run_id)
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.post("/api/projects/{project_id}/chapters/{chapter}/apply-repair")
    def apply_repair(project_id: str, chapter: int, payload: dict[str, Any]):
        try:
            return service.apply_repair(store, project_id, chapter, str(payload.get("run_id") or ""))
        except LocalStoreError as exc:
            raise as_http_error(exc)

    static_dir = Path(__file__).resolve().parents[3] / "web" / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return app


def run_web_command(args: argparse.Namespace, settings: Settings | None = None) -> int:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install the web extra first: pip install -e '.[web]'") from exc

    app = make_app(settings, mock=bool(args.mock))
    uvicorn.run(app, host=args.host, port=args.port)
    return 0

