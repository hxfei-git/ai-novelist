from __future__ import annotations

import types

from fastapi.testclient import TestClient

from ai_novelist.cli import build_parser
from ai_novelist.config import Settings
from ai_novelist.web import app as web_app


def test_web_parser_accepts_provider_model_and_timeout() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "web",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--timeout",
            "180",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
    )

    assert args.provider == "deepseek"
    assert args.model == "deepseek-chat"
    assert args.timeout == 180




def test_web_app_exposes_outline_action_and_workspace_routes(tmp_path) -> None:
    app = web_app.make_app(Settings(projects_dir=tmp_path), mock=True)
    routes = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/projects/{project_id}/outline/stages/{stage}/generate" in routes
    assert "/api/projects/{project_id}/outline/stages/{stage}/revise" in routes
    assert "/api/projects/{project_id}/outline/stages/{stage}/lock" in routes
    assert "/api/projects/{project_id}/outline/stages/{stage}/pending" in routes
    assert "/api/projects/{project_id}/outline/stages/{stage}/pending/submit" in routes
    assert "/api/projects/{project_id}/outline/chapter-workspace" in routes
    assert "/api/projects/{project_id}/outline/chapter-workspace/volumes/{volume_index}/generate" in routes
    assert "/api/projects/{project_id}/outline/chapter-workspace/volumes/{volume_index}/revise" in routes
    assert "/api/projects/{project_id}/outline/chapter-workspace/volumes/{volume_index}/lock" in routes
    assert not any("/action" in path for path in routes)


def test_generic_chapter_outline_stage_get_returns_workspace_error(tmp_path) -> None:
    client = TestClient(web_app.make_app(Settings(projects_dir=tmp_path), mock=True))
    created = client.post("/api/projects", json={"title": "Web Demo", "project_id": "web-demo"})
    assert created.status_code == 200

    response = client.get("/api/projects/web-demo/outline/stages/chapter_outline")

    assert response.status_code == 400
    assert "章节大纲工作区" in response.json()["detail"]




def test_project_idea_and_progress_log_endpoints_are_project_scoped(tmp_path) -> None:
    client = TestClient(web_app.make_app(Settings(projects_dir=tmp_path), mock=True))
    created = client.post("/api/projects", json={"title": "Idea Web", "project_id": "idea-web"})
    assert created.status_code == 200

    idea_response = client.post("/api/projects/idea-web/idea", json={"idea": "月球城市失忆工程师"})
    assert idea_response.status_code == 200
    assert idea_response.json()["idea"] == "月球城市失忆工程师"

    progress_response = client.put("/api/projects/idea-web/progress-log", json={"items": ["方向定位开始", "保存创意"]})
    assert progress_response.status_code == 200
    assert progress_response.json()["items"] == ["方向定位开始", "保存创意"]

    loaded = client.get("/api/projects/idea-web/progress-log")
    assert loaded.status_code == 200
    assert loaded.json()["items"] == ["方向定位开始", "保存创意"]


def test_outline_stage_pending_api_returns_recommended_options(tmp_path) -> None:
    client = TestClient(web_app.make_app(Settings(projects_dir=tmp_path), mock=True))
    created = client.post("/api/projects", json={"title": "Web Demo", "project_id": "web-demo"})
    assert created.status_code == 200
    state = client.get("/api/projects/web-demo/state").json()
    state["outline_stage_artifacts"]["direction"] = {
        "stage": "direction",
        "status": "options_ready",
        "pending_questions": ["主角是否保留灰色动机？——推荐方案：保留灰色动机，但仅作为秘密揭露的驱动力。"],
    }
    (tmp_path / "web-demo" / "state.json").write_text(__import__("json").dumps(state, ensure_ascii=False), encoding="utf-8")

    response = client.get("/api/projects/web-demo/outline/stages/direction/pending")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["question"] == "主角是否保留灰色动机？"
    assert payload["items"][0]["options"][0]["label"] == "采纳推荐方案"
    assert payload["items"][0]["options"][0]["answer"] == "保留灰色动机，但仅作为秘密揭露的驱动力。"
    assert [option["id"] for option in payload["items"][0]["options"]] == ["accept", "defer", "custom"]


def test_run_web_command_passes_generation_defaults(monkeypatch, tmp_path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "web",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--timeout",
            "180",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
    )
    captured = {}

    def fake_make_app(settings, *, mock=False, provider=None, model=None, timeout=None):
        captured["settings"] = settings
        captured["mock"] = mock
        captured["provider"] = provider
        captured["model"] = model
        captured["timeout"] = timeout
        return object()

    fake_uvicorn = types.SimpleNamespace(run=lambda app, host, port: captured.update({"host": host, "port": port}))

    monkeypatch.setattr(web_app, "make_app", fake_make_app)
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", fake_uvicorn)

    result = web_app.run_web_command(args, Settings(projects_dir=tmp_path))

    assert result == 0
    assert captured["provider"] == "deepseek"
    assert captured["model"] == "deepseek-chat"
    assert captured["timeout"] == 180
    assert captured["mock"] is False
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8000
