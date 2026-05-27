from __future__ import annotations

import pytest

from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError, AgentCallOptions
from ai_novelist.storage.local_store import LocalStore, LocalStoreError
from ai_novelist.web import service


class DummyAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "global_consistency_repair" in prompt:
            return "# repaired chapter\n\n修复后的章节正文，保留原章节事件并补齐连续性。"
        return "{}"


class ModelReviewAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        assert "global_consistency_reviewer" in prompt
        assert "Chapter 1" in prompt
        return (
            '{"status":"needs_repair","summary":"模型发现连续性问题。",'
            '"issues":[{"severity":"serious","chapter":1,"category":"timeline",'
            '"message":"第 1 章结尾与第 2 章开场时间线冲突。"}]}'
        )


class FailingReviewAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "global_consistency_reviewer" in prompt:
            raise AgentAdapterError("model unavailable")
        return "{}"


class OutlineReviewAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "outline_editor" in prompt:
            return (
                "STATUS: revise\nQUALITY_SCORE: 72\n"
                "## 总体判断\n章节大纲缺少结尾收束。\n\n"
                "## 主要问题\n- 章节列表总表偏概括。\n\n"
                "## 修改建议\n- 补强最后一卷的收束钩子。\n"
            )
        if "outline_reviser" in prompt:
            return "# 最终锁定总大纲\n\n## 方向定位\n已补强结尾收束。"
        if "version_comparator" in prompt:
            return "# 大纲版本比较\n\n修订补强了结尾收束。"
        return "{}"


class CapturingOutlineReviewAdapter(AgentAdapter):
    def __init__(self) -> None:
        self.reviser_prompt = ""

    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "outline_reviser" in prompt:
            self.reviser_prompt = prompt
            return "# 最终锁定总大纲\n\n## 方向定位\n只采纳选中建议。"
        if "version_comparator" in prompt:
            return "# 大纲版本比较\n\n只应用选中建议。"
        return "{}"


def test_project_and_outline_stage_file_roundtrip(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = service.create_project(store, "Web Demo", "web-demo", idea="一个显式流程控制的小说项目")

    projects = service.list_projects(store)
    assert [item.project_id for item in projects] == ["web-demo"]
    assert store.load_state(state.project_id).idea == "一个显式流程控制的小说项目"

    saved = service.save_outline_stage_content(store, "web-demo", "worldbuilding", "# 世界观设定\n\n规则清晰。")
    assert saved["status"] == "options_ready"
    assert "规则清晰" in saved["content"]

    reloaded = store.load_state("web-demo")
    assert reloaded.outline_stage_artifacts["worldbuilding"]["status"] == "options_ready"
    assert "规则清晰" in store.load_outline_artifact("web-demo", "worldbuilding")
    assert "规则清晰" in store.worldbuilding_path("web-demo").read_text(encoding="utf-8")




def test_project_onboarding_requires_idea_or_existing_outline_context(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = service.create_project(store, "Onboarding Demo", "onboarding-demo")

    assert service.project_needs_onboarding(state) is True

    state.idea = "月球城市失忆工程师追查自己的小说手稿"
    store.save_state(state)

    assert service.project_needs_onboarding(store.load_state("onboarding-demo")) is False


def test_save_project_idea_persists_onboarding_seed(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    service.create_project(store, "Idea Demo", "idea-demo")

    state = service.save_project_idea(store, "idea-demo", "  赛博唐代女仵作悬疑故事  ")

    assert state.idea == "赛博唐代女仵作悬疑故事"
    assert store.load_state("idea-demo").idea == "赛博唐代女仵作悬疑故事"


def test_project_progress_log_is_project_scoped_and_file_backed(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    service.create_project(store, "Progress A", "progress-a")
    service.create_project(store, "Progress B", "progress-b")

    service.save_project_progress_log(store, "progress-a", ["A2", "A1"])
    service.save_project_progress_log(store, "progress-b", ["B1"])

    assert service.load_project_progress_log(store, "progress-a") == ["A2", "A1"]
    assert service.load_project_progress_log(store, "progress-b") == ["B1"]
    assert (store.project_dir("progress-a") / "web_progress_log.json").exists()


def test_generate_outline_stage_uses_explicit_full_generation_intent_with_existing_content(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "options_ready"}
    store.save_outline_artifact(state, "characters", "# 人物关系\n\n已有草案。\n")
    store.save_state(state)
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured.update(data)
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    state = service.generate_outline_stage(store, DummyAdapter(), "web-demo", "characters", "补强人物关系")

    assert captured["outline_stage"] == "characters"
    assert captured["director_intent"] == "create"
    assert captured["revision_instruction"] == ""
    assert state.director_action == "run_outline_stage"
    assert state.user_request == "补强人物关系"


def test_outline_stage_list_hides_review_lock(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["direction"] = {"stage": "direction", "label": "方向定位", "status": "locked", "summary": "方向"}
    state.outline_stage_artifacts["review_lock"] = {"stage": "review_lock", "label": "审稿锁定", "status": "options_ready", "summary": "旧审查"}
    state.outline_stage_artifacts["chapter_outline"] = {"stage": "chapter_outline", "status": "options_ready"}
    store.save_state(state)

    stages = service.outline_stage_list(store, "web-demo")

    assert all(item["stage"] != "review_lock" for item in stages)
    assert all(item["stage"] != "chapter_outline" for item in stages)




def test_outline_stage_payload_includes_action_state(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "worldbuilding"
    state.outline_stage_artifacts["worldbuilding"] = {
        "stage": "worldbuilding",
        "label": "世界观设定",
        "status": "options_ready",
        "summary": "世界观草案。",
        "pending_questions": ["地理边界是否锁定？"],
    }
    store.save_outline_artifact(state, "worldbuilding", "# 世界观设定\n\n已有草案。\n")
    store.save_state(state)

    payload = service.outline_stage_payload(store, state, "worldbuilding")

    assert payload["stage"] == "worldbuilding"
    assert payload["action_state"]["can_generate"] is True
    assert payload["action_state"]["can_revise"] is True
    assert payload["action_state"]["can_lock"] is False
    assert "待确认问题" in payload["action_state"]["lock_reason"]



def test_load_outline_stage_payload_rejects_chapter_outline_workspace(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")

    with pytest.raises(LocalStoreError, match="章节大纲工作区"):
        service.load_outline_stage_payload(store, "web-demo", "chapter_outline")


def test_outline_stage_payload_disables_revise_without_content(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "characters"
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "collecting"}
    store.save_state(state)

    payload = service.outline_stage_payload(store, state, "characters")

    assert payload["action_state"]["can_revise"] is False


def test_revise_outline_stage_rejects_stage_without_content(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")

    with pytest.raises(LocalStoreError, match="没有可修订内容"):
        service.revise_outline_stage(store, DummyAdapter(), "web-demo", "characters", "细化角色")


def test_outline_stage_payload_marks_locked_stage_as_locked(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "characters"
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "label": "人物关系",
        "status": "locked",
        "summary": "人物关系已锁定。",
        "pending_questions": [],
        "locked_at": "2026-05-27T12:00:00+00:00",
    }
    store.save_state(state)

    payload = service.outline_stage_payload(store, state, "characters")

    assert payload["action_state"]["can_generate"] is False
    assert payload["action_state"]["can_revise"] is False
    assert payload["action_state"]["can_lock"] is False
    assert payload["action_state"]["lock_reason"] == "已锁定"


@pytest.mark.parametrize("action", ["save", "generate", "revise"])
def test_locked_outline_stage_rejects_mutations(action: str, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "locked"}
    store.save_state(state)

    with pytest.raises(LocalStoreError, match="已锁定"):
        if action == "save":
            service.save_outline_stage_content(store, "web-demo", "characters", "# 人物关系\n\n改稿。")
        elif action == "generate":
            service.generate_outline_stage(store, DummyAdapter(), "web-demo", "characters")
        else:
            service.revise_outline_stage(store, DummyAdapter(), "web-demo", "characters", "改稿")


@pytest.mark.parametrize("action", ["save", "generate", "revise", "lock"])
def test_generic_outline_stage_mutations_reject_chapter_outline_workspace(action: str, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {"stage": "chapter_outline", "status": "options_ready"}
    store.save_outline_artifact(state, "chapter_outline", "## 第一卷\n\n已有章纲。\n")
    store.save_state(state)

    with pytest.raises(LocalStoreError, match="章节大纲工作区"):
        if action == "save":
            service.save_outline_stage_content(store, "web-demo", "chapter_outline", "## 第一卷\n\n改稿。")
        elif action == "generate":
            service.generate_outline_stage(store, DummyAdapter(), "web-demo", "chapter_outline")
        elif action == "revise":
            service.revise_outline_stage(store, DummyAdapter(), "web-demo", "chapter_outline", "改稿")
        else:
            service.lock_outline_stage(store, DummyAdapter(), "web-demo", "chapter_outline")


def test_outline_stage_payload_allows_lock_without_real_pending_questions(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "status": "options_ready",
        "pending_questions": ["暂无，当前阶段可继续修改或确认进入下一阶段。"],
    }
    store.save_state(state)

    payload = service.outline_stage_payload(store, state, "characters")

    assert payload["action_state"]["can_lock"] is True
    assert payload["action_state"]["lock_reason"] == ""


def test_chapter_outline_workspace_payload_includes_volume_navigation(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["volume_outline"] = {
        "stage": "volume_outline",
        "label": "分卷大纲",
        "status": "locked",
        "summary": "三卷结构。",
        "metadata": {"total_volumes": 3, "current_volume_index": 2, "completed_volumes": [1]},
    }
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "label": "章节大纲",
        "status": "options_ready",
        "summary": "第二卷章节大纲草案。",
        "metadata": {
            "total_volumes": 3,
            "current_volume_index": 2,
            "completed_volumes": [1],
            "volume_statuses": {"1": "locked", "2": "options_ready", "3": "collecting"},
        },
    }
    store.save_outline_artifact(
        state,
        "chapter_outline",
        """## 第一卷

### 第 1 章：开端
旧内容。

## 第二卷：转折

### 第 2 章：中段
当前卷内容。

## 第三卷

### 第 3 章：收束
后续内容。
""",
    )
    store.save_outline_artifact(
        state,
        "volume_outline",
        """## 第一卷：开端

## 第二卷：转折

## 第三卷：收束
""",
    )
    store.save_state(state)

    payload = service.chapter_outline_workspace_payload(store, "web-demo", selected_volume_index=2)

    assert payload["current_volume_index"] == 2
    assert len(payload["volume_specs"]) == 3
    assert payload["completed_volumes"] == [1]
    assert payload["volume_statuses"]["2"] == "options_ready"
    assert payload["selected_volume"]["index"] == 2
    assert payload["selected_volume"]["label"] == "第二卷"
    assert payload["selected_volume"]["name"] == "转折"
    assert payload["selected_volume"]["status"] == "options_ready"
    assert "第二卷" in payload["selected_volume"]["content"]
    assert "第一卷" not in payload["selected_volume"]["content"]
    assert "第三卷" not in payload["selected_volume"]["content"]
    assert payload["selected_volume"]["can_generate"] is True
    assert payload["selected_volume"]["can_revise"] is True
    assert payload["selected_volume"]["can_lock"] is True
    assert payload["selected_volume"]["lock_reason"] == ""


def test_chapter_outline_workspace_payload_selects_requested_volume(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "options_ready",
        "metadata": {
            "total_volumes": 2,
            "current_volume_index": 2,
            "completed_volumes": [1],
            "volume_statuses": {"1": "locked", "2": "options_ready"},
            "volume_contents": {"1": "### 第一卷\n\n已确认内容。", "2": "### 第二卷\n\n待确认内容。"},
        },
    }
    store.save_outline_artifact(state, "volume_outline", "## 第一卷：开局\n\n## 第二卷：收束\n")
    store.save_state(state)

    payload = service.chapter_outline_workspace_payload(store, "web-demo", selected_volume_index=1)

    assert payload["current_volume_index"] == 2
    assert payload["selected_volume"]["index"] == 1
    assert payload["selected_volume"]["status"] == "locked"
    assert payload["selected_volume"]["content"] == "### 第一卷\n\n已确认内容。"
    assert payload["selected_volume"]["can_lock"] is False
    assert payload["selected_volume"]["lock_reason"] == "已锁定"


def test_chapter_outline_workspace_payload_rejects_invalid_volume(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")

    with pytest.raises(LocalStoreError, match="Unknown chapter outline volume: 0"):
        service.chapter_outline_workspace_payload(store, "web-demo", selected_volume_index=0)


def test_chapter_outline_workspace_extracts_non_current_volume_from_combined_content(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "options_ready",
        "metadata": {
            "total_volumes": 2,
            "current_volume_index": 2,
            "completed_volumes": [1],
            "volume_statuses": {"1": "locked", "2": "options_ready"},
        },
    }
    store.save_outline_artifact(
        state,
        "volume_outline",
        "## 第一卷：开局\n\n## 第二卷：收束\n",
    )
    store.save_outline_artifact(
        state,
        "chapter_outline",
        "## 第一卷：开局\n\n### 第 1 章：出发\n旧内容。\n\n## 第二卷：收束\n\n### 第 2 章：归来\n新内容。\n",
    )
    store.save_state(state)

    payload = service.chapter_outline_workspace_payload(store, "web-demo", selected_volume_index=1)

    assert "第一卷" in payload["selected_volume"]["content"]
    assert "第二卷" not in payload["selected_volume"]["content"]


def test_extract_stage_pending_questions_from_markdown_filters_status_lines() -> None:
    markdown = """# 人物关系

## 十三、待确认问题
1. 沈灵儿决裂的3-5章小纲是否需要在章节规划阶段提前完成？——影响R02中期演化强度。
2. 林霄的1-2个专属视角章的具体内容方向是否需提前规划？——影响正魔反转说服力。
暂无，当前阶段可继续修改或确认进入下一阶段。

## 仍需确认的问题
- 暂无，当前阶段可继续修改或确认进入下一阶段。
"""

    questions = service.extract_pending_questions_from_stage_markdown(markdown)

    assert questions == [
        "沈灵儿决裂的3-5章小纲是否需要在章节规划阶段提前完成？——影响R02中期演化强度。",
        "林霄的1-2个专属视角章的具体内容方向是否需提前规划？——影响正魔反转说服力。",
    ]


def test_outline_stage_pending_payload_prefers_artifact_questions(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "characters"
    state.pending_questions = ["请确认是否锁定人物关系并进入下一阶段，或继续提出修改。"]
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "status": "options_ready",
        "pending_questions": ["artifact question?"],
    }
    store.save_outline_artifact(state, "characters", "## 十三、待确认问题\n1. markdown question?\n")
    store.save_state(state)

    payload = service.outline_stage_pending_payload(store, "web-demo", "characters")

    assert payload["project_id"] == "web-demo"
    assert payload["stage"] == "characters"
    assert [item["question"] for item in payload["items"]] == ["artifact question?"]
    assert payload["items"][0]["options"][0]["id"] == "accept"
    assert [option["id"] for option in payload["items"][0]["options"]] == ["accept", "defer", "custom"]


def test_pending_options_show_concrete_recommendation_and_custom_path() -> None:
    options = service.default_pending_options("主角是否保留灰色动机？", "direction")

    assert options[0]["label"] == "采纳推荐方案"
    assert "主角是否保留灰色动机" in options[0]["answer"]
    assert "采纳当前建议" not in options[0]["answer"]
    assert options[1]["label"] == "暂不确定"
    assert options[2]["label"] == "我的建议"
    assert options[2]["requires_input"] is True


def test_pending_options_use_recommendation_embedded_in_question() -> None:
    options = service.default_pending_options(
        "主角是否保留灰色动机？——推荐方案：保留灰色动机，但仅作为秘密揭露的驱动力。",
        "direction",
    )

    assert options[0]["answer"] == "保留灰色动机，但仅作为秘密揭露的驱动力。"


def test_pending_options_use_actionable_legacy_question_suffix() -> None:
    options = service.default_pending_options(
        "最终战隐藏据点势力是否有具体来源？——若不归渊遗民已覆盖，则无需额外设定。",
        "characters",
    )

    assert options[0]["answer"] == "若不归渊遗民已覆盖，则无需额外设定。"


def test_outline_stage_pending_payload_falls_back_to_markdown(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "characters"
    state.pending_questions = ["请确认是否锁定人物关系并进入下一阶段，或继续提出修改。"]
    store.save_outline_artifact(
        state,
        "characters",
        "## 十三、待确认问题\n"
        "1. 最终战隐藏据点势力是否有具体来源？——若不归渊遗民已覆盖，则无需额外设定。\n",
    )
    store.save_state(state)

    payload = service.outline_stage_pending_payload(store, "web-demo", "characters")

    assert [item["question"] for item in payload["items"]] == [
        "最终战隐藏据点势力是否有具体来源？——若不归渊遗民已覆盖，则无需额外设定。"
    ]
    assert payload["items"][0]["id"]
    assert any(option["label"] == "采纳推荐方案" for option in payload["items"][0]["options"])


def test_outline_review_roundtrip_and_apply_updates_outline(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 方向定位\n旧稿。"
    store.save_state(state)

    report = service.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")
    assert report["decision"] == "revise"
    assert report["score"] == 72
    latest = service.latest_outline_review_report(store, "web-demo")
    assert latest["run_id"] == report["run_id"]

    applied = service.apply_outline_review(store, OutlineReviewAdapter(), "web-demo", report["run_id"])

    assert applied["applied"] is True
    assert store.outline_path("web-demo").exists()
    saved = store.load_state("web-demo")
    assert saved.outline_review_applied_run_id == report["run_id"]
    assert saved.outline_review_run_id == report["run_id"]


def test_outline_review_report_exposes_selectable_suggestions(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 章节大纲\n旧稿。"
    store.save_state(state)

    report = service.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")

    suggestions = report["repair_suggestions"]
    assert suggestions
    assert suggestions[0]["id"]
    assert suggestions[0]["selected"] is True
    assert "章节列表总表偏概括" in suggestions[0]["message"]
    assert any("补强最后一卷的收束钩子" in item["recommendation"] for item in suggestions)


def test_apply_outline_review_uses_only_selected_suggestions(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 章节大纲\n旧稿。"
    store.save_state(state)
    report = service.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")
    suggestions = report["repair_suggestions"]
    selected = next(item for item in suggestions if "补强最后一卷" in item["recommendation"])
    unselected = next(item for item in suggestions if item["id"] != selected["id"])
    adapter = CapturingOutlineReviewAdapter()

    service.apply_outline_review(
        store,
        adapter,
        "web-demo",
        report["run_id"],
        selected_issue_ids=[selected["id"]],
    )

    assert selected["recommendation"] in adapter.reviser_prompt
    assert unselected["message"] not in adapter.reviser_prompt
    assert unselected["recommendation"] not in adapter.reviser_prompt


def test_submit_stage_pending_answers_builds_revision_instruction(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "status": "options_ready",
        "pending_questions": ["林霄视角章是否需提前规划？"],
    }
    store.save_outline_artifact(state, "characters", "# 人物关系\n\n已有草案。\n")
    store.save_state(state)
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured["data"] = dict(data)
        data["outline_stage_artifacts"] = {
            **data.get("outline_stage_artifacts", {}),
            "characters": {
                "stage": "characters",
                "status": "options_ready",
                "pending_questions": [],
            },
        }
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    result = service.submit_stage_pending_answers(
        store,
        DummyAdapter(),
        "web-demo",
        "characters",
        [
            {
                "question": "林霄视角章是否需提前规划？",
                "selected_option_id": "accept",
                "answer": "采纳当前建议，提前规划1-2个专属视角章。",
            }
        ],
    )

    assert result.outline_stage == "characters"
    assert captured["data"]["director_action"] == "run_outline_stage"
    assert "针对当前阶段待确认项" in captured["data"]["revision_instruction"]
    assert "林霄视角章是否需提前规划？" in captured["data"]["revision_instruction"]
    assert "提前规划1-2个专属视角章" in captured["data"]["revision_instruction"]


def test_submit_stage_pending_answers_rejects_locked_stage(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "locked"}
    store.save_state(state)

    with pytest.raises(LocalStoreError, match="已锁定"):
        service.submit_stage_pending_answers(
            store,
            DummyAdapter(),
            "web-demo",
            "characters",
            [{"question": "角色关系？", "answer": "保持当前设定。"}],
        )


def test_submit_stage_pending_answers_rejects_chapter_outline_workspace(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")

    with pytest.raises(LocalStoreError, match="章节大纲工作区"):
        service.submit_stage_pending_answers(
            store,
            DummyAdapter(),
            "web-demo",
            "chapter_outline",
            [{"question": "本卷顺序？", "answer": "保持当前顺序。"}],
        )


def test_submit_stage_pending_answers_rejects_missing_content(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "options_ready"}
    store.save_state(state)

    with pytest.raises(LocalStoreError, match="没有可修订内容"):
        service.submit_stage_pending_answers(
            store,
            DummyAdapter(),
            "web-demo",
            "characters",
            [{"question": "问题？", "answer": "保持当前设定。"}],
        )


def test_submit_stage_pending_answers_rejects_incomplete_answer(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    store.save_outline_artifact(state, "characters", "# 人物关系\n\n已有草案。\n")
    store.save_state(state)

    with pytest.raises(LocalStoreError, match="每条待确认项都需要选择默认方案或填写自定义答案"):
        service.submit_stage_pending_answers(
            store,
            DummyAdapter(),
            "web-demo",
            "characters",
            [{"question": "问题？", "selected_option_id": "", "answer": ""}],
        )


def test_revise_outline_stage_sets_revision_intent(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "options_ready"}
    store.save_outline_artifact(state, "characters", "# 人物关系\n\n已有草案。\n")
    store.save_state(state)
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured.update(data)
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    state = service.revise_outline_stage(store, DummyAdapter(), "web-demo", "characters", "收紧人物关系")

    assert state.director_intent == "revise"
    assert captured["revision_instruction"] == "收紧人物关系"
    assert captured["director_action"] == "run_outline_stage"


def test_lock_outline_stage_rejects_real_pending_questions(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "status": "options_ready",
        "pending_questions": ["主角关系是否定稿？"],
    }
    store.save_state(state)

    with pytest.raises(LocalStoreError, match="待确认问题"):
        service.lock_outline_stage(store, DummyAdapter(), "web-demo", "characters")


def test_lock_outline_stage_rejects_already_locked_stage(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "locked"}
    store.save_state(state)

    with pytest.raises(LocalStoreError, match="已锁定"):
        service.lock_outline_stage(store, DummyAdapter(), "web-demo", "characters")


def make_selectable_chapter_workspace(store: LocalStore) -> None:
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "locked",
        "pending_questions": ["第二卷是否锁定？"],
        "metadata": {
            "total_volumes": 2,
            "current_volume_index": 2,
            "completed_volumes": [],
            "volume_statuses": {"1": "options_ready", "2": "locked"},
            "volume_contents": {"1": "### 第一卷\n\n可操作内容。", "2": "### 第二卷\n\n已锁定内容。"},
        },
    }
    store.save_outline_artifact(state, "volume_outline", "## 第一卷：开局\n\n## 第二卷：收束\n")
    store.save_state(state)


def test_non_current_options_ready_volume_payload_matches_action_refusal(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    make_selectable_chapter_workspace(store)

    payload = service.chapter_outline_workspace_payload(store, "web-demo", selected_volume_index=1)
    selected = payload["selected_volume"]

    assert selected["status"] == "options_ready"
    assert selected["can_generate"] is False
    assert selected["can_revise"] is False
    assert selected["can_lock"] is False
    assert selected["lock_reason"] == "请先完成当前卷"

    with pytest.raises(LocalStoreError, match=selected["lock_reason"]):
        service.generate_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1)


@pytest.mark.parametrize("action", ["generate", "revise", "lock"])
def test_chapter_outline_volume_actions_reject_non_current_volume(action: str, monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    make_selectable_chapter_workspace(store)
    called = {"run": False}

    def fail_run(*args, **kwargs):
        called["run"] = True
        raise AssertionError("graph must not execute for a non-current volume")

    monkeypatch.setattr(service, "run_outline_stage_node", fail_run)
    monkeypatch.setattr(service, "advance_outline_stage_node", fail_run)

    with pytest.raises(LocalStoreError, match="请先完成当前卷"):
        if action == "generate":
            service.generate_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1)
        elif action == "revise":
            service.revise_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1, "细化第一卷")
        else:
            service.lock_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1)

    assert called["run"] is False
    saved = store.load_state("web-demo")
    assert saved.outline_stage_artifacts["chapter_outline"]["metadata"]["current_volume_index"] == 2


def test_chapter_outline_locked_current_volume_cannot_be_regenerated(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    make_selectable_chapter_workspace(store)

    with pytest.raises(LocalStoreError, match="已锁定"):
        service.generate_chapter_outline_volume(store, DummyAdapter(), "web-demo", 2)


def test_generate_current_chapter_outline_volume_sets_default_current_index(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "collecting",
        "metadata": {"total_volumes": 1, "volume_statuses": {"1": "collecting"}},
    }
    store.save_outline_artifact(state, "volume_outline", "## 第一卷：开局\n")
    store.save_state(state)
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured.update(data)
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    service.generate_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1)

    assert captured["outline_stage_artifacts"]["chapter_outline"]["metadata"]["current_volume_index"] == 1


def test_generate_current_chapter_outline_volume_uses_full_generation_intent_with_existing_content(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "options_ready",
        "metadata": {
            "total_volumes": 1,
            "current_volume_index": 1,
            "volume_statuses": {"1": "options_ready"},
            "volume_contents": {"1": "### 第一卷\n\n已有章纲。"},
        },
    }
    store.save_outline_artifact(state, "volume_outline", "## 第一卷：开局\n")
    store.save_state(state)
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured.update(data)
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    service.generate_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1, "重建第一卷")

    assert captured["director_intent"] == "create"
    assert captured["revision_instruction"] == ""
    assert captured["user_request"] == "重建第一卷"


def test_revise_current_chapter_outline_volume_uses_existing_content(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "options_ready",
        "metadata": {
            "total_volumes": 1,
            "current_volume_index": 1,
            "volume_statuses": {"1": "options_ready"},
            "volume_contents": {"1": "### 第一卷\n\n已有章纲。"},
        },
    }
    store.save_outline_artifact(state, "volume_outline", "## 第一卷：开局\n")
    store.save_state(state)
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured.update(data)
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    service.revise_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1, "细化第一卷")

    assert captured["outline_stage_artifacts"]["chapter_outline"]["metadata"]["current_volume_index"] == 1
    assert captured["director_intent"] == "revise"


def test_revise_current_chapter_outline_volume_rejects_missing_content(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "collecting",
        "metadata": {
            "total_volumes": 1,
            "current_volume_index": 1,
            "volume_statuses": {"1": "collecting"},
        },
    }
    store.save_outline_artifact(state, "volume_outline", "## 第一卷：开局\n")
    store.save_state(state)

    payload = service.chapter_outline_workspace_payload(store, "web-demo", selected_volume_index=1)
    assert payload["selected_volume"]["can_revise"] is False

    with pytest.raises(LocalStoreError, match="没有可修订内容"):
        service.revise_chapter_outline_volume(store, DummyAdapter(), "web-demo", 1, "细化第一卷")


def test_chapter_batch_payload_sets_director_task_args(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")
    captured = {}

    class FakeGraph:
        def invoke(self, data: dict) -> dict:
            captured.update(data["director_task_args"])
            return data

    monkeypatch.setattr(service, "build_volume_write_graph", lambda adapter, store, progress=None: FakeGraph())

    service.generate_chapter_batch(store, DummyAdapter(), "web-demo", volume=2, chapters="1-3", max_workers=4)

    assert captured == {"volume": 2, "chapters": "1-3"}


def test_global_review_and_repair_are_explicit_apply(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "短"
    store.save_chapter_draft(state, version=1)
    original = store.chapter_draft_path("web-demo", 1, 1).read_text(encoding="utf-8")

    report = service.review_all_chapters(store, DummyAdapter(), "web-demo")
    assert report["status"] == "needs_repair"
    assert store.chapter_draft_path("web-demo", 1, 1).read_text(encoding="utf-8") == original
    suggestions = report["repair_suggestions"]
    assert suggestions[0]["chapter"] == 1
    assert suggestions[0]["selected"] is True
    assert not store.chapter_draft_path("web-demo", 1, 2).exists()

    proposals = service.generate_repair_proposals(store, DummyAdapter(), "web-demo", report["run_id"])
    assert proposals["proposals"][0]["recommendation"]

    applied = service.apply_repair(store, DummyAdapter(), "web-demo", 1, report["run_id"], selected_issue_ids=[suggestions[0]["id"]])
    assert applied["version"] == 2
    assert store.chapter_draft_path("web-demo", 1, 2).exists()


def test_chapter_list_and_detail_prefer_final_then_highest_draft_then_legacy(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")

    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "# 第 1 章草稿五\n\n这是第五版草稿正文，用于确认最高版本读取。"
    store.save_chapter_draft(state, version=5)
    state.current_final_chapter = "# 第 1 章定稿\n\n这是定稿正文，应该优先于所有草稿。"
    store.save_final_chapter(state)

    state.active_chapter = 2
    state.current_chapter = 2
    state.chapter_draft = "# 第 2 章草稿一\n\n旧草稿。"
    store.save_chapter_draft(state, version=1)
    state.chapter_draft = "# 第 2 章草稿十二\n\n最高编号草稿，应该被选为最新正文。"
    store.save_chapter_draft(state, version=12)

    state.active_chapter = 3
    state.current_chapter = 3
    state.chapter_draft = "# 第 3 章旧路径\n\n只有 legacy chapter_003.md 时也能读取。"
    store.save_chapter(state)

    chapters = service.list_chapters(store, "web-demo")

    assert [item["chapter"] for item in chapters] == [1, 2, 3]
    assert chapters[0]["source"] == "final"
    assert chapters[0]["version"] is None
    assert chapters[1]["source"] == "draft"
    assert chapters[1]["version"] == 12
    assert chapters[2]["source"] == "legacy"

    first = service.load_chapter_payload(store, "web-demo", 1)
    second = service.load_chapter_payload(store, "web-demo", 2)
    third = service.load_chapter_payload(store, "web-demo", 3)

    assert "定稿正文" in first["content"]
    assert first["path"] == "chapters/chapter_001/final.md"
    assert "最高编号草稿" in second["content"]
    assert second["path"] == "chapters/chapter_002/draft_v12.md"
    assert "旧路径" in third["content"]
    assert third["path"] == "chapters/chapter_003.md"

def test_global_review_uses_model_consistency_report(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    store.save_outline_artifact(state, "chapter_outline", "# 章节大纲\n\n第一章进入雨城，第二章当天夜里继续。")
    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "# 第 1 章\n\n" + "雨城的夜色压在港口上，主角追踪线索并在钟楼下确认了同伴留下的暗号。" * 4
    store.save_chapter_draft(state, version=1)

    report = service.review_all_chapters(store, ModelReviewAdapter(), "web-demo")

    assert report["status"] == "needs_repair"
    assert report["review_source"] == "model"
    assert report["summary"] == "模型发现连续性问题。"
    assert any(item["category"] == "timeline" for item in report["issues"])
    assert report["repair_suggestions"][0]["selected"] is True
    assert "前后章节" in report["repair_suggestions"][0]["recommendation"]
    saved = service.latest_global_review(store, "web-demo")
    assert saved["run_id"] == report["run_id"]


def test_global_review_falls_back_to_local_scan_on_model_error(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.active_chapter = 1
    state.current_chapter = 1
    state.chapter_draft = "# 第 1 章\n\n" + "TODO：这里待补完整正文。" * 6
    store.save_chapter_draft(state, version=1)

    report = service.review_all_chapters(store, FailingReviewAdapter(), "web-demo")

    assert report["review_source"] == "local"
    assert any(item["category"] == "placeholder" for item in report["issues"])
    assert any(item["category"] == "model_review_error" for item in report["issues"])
