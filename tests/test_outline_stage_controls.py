from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.director_service import DirectorDecision, DirectorService
from ai_novelist.outline.legacy_migration import ensure_outline_stage
from ai_novelist.outline.question_filter import filter_stage_confirmation_questions
from ai_novelist.outline.stage_contracts import OUTLINE_STAGES, get_stage_contract
from ai_novelist.outline.stage_guard import detect_formulaic_causality, guard_stage_output
from ai_novelist.research import MockSearchBackend
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_active_outline_stages_exclude_concept():
    assert "concept" not in OUTLINE_STAGES
    assert OUTLINE_STAGES == [
        "direction",
        "worldbuilding",
        "characters",
        "story_flow",
        "volume_outline",
        "chapter_outline",
        "review_lock",
    ]


def test_stage_contracts_have_active_stages_only():
    for stage in OUTLINE_STAGES:
        contract = get_stage_contract(stage)
        assert contract.key == stage
        assert contract.purpose
        assert contract.slots
    assert get_stage_contract("concept").key == "direction"


def test_direction_guard_demotes_unsupported_concrete_memory_cost():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门底层弟子，苟道藏锋")
    text = "## 方向定位稿\n- 每一次动用前世记忆都需付出预支的代价，可能消耗生命力。"
    result = guard_stage_output(text, "direction", state)
    assert "每一次" not in result.text
    assert "消耗生命力" not in result.text
    assert result.text.strip() == "## 方向定位稿"


def test_direction_guard_preserves_user_explicit_cost_at_high_level():
    state = NovelState(project_id="demo", title="Demo", idea="主角用前世记忆会消耗寿命")
    text = "## 方向定位稿\n- 前世记忆会消耗寿命，所以主角不能滥用。"
    result = guard_stage_output(text, "direction", state)
    assert "寿命" in result.text or "具体限制留" in result.text


def test_formulaic_causality_detection_is_pattern_based():
    cases = [
        "每一次示弱都是邀请他人掠夺。",
        "每次动用都会招来新的敌人。",
        "凡是求稳必然付出代价。",
        "一旦保护别人就会被世界收债。",
    ]
    for bad in cases:
        issues = detect_formulaic_causality(bad)
        assert any(issue.code == "formulaic_absolute_causality" for issue in issues)


def test_worldbuilding_guard_rejects_abstract_mechanism_language():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门底层弟子")
    text = "## 世界观设定稿\n## 代价红线\n前世记忆有债必偿，情感变量超过阈值会触发羁绊抵押。"
    result = guard_stage_output(text, "worldbuilding", state)
    for bad in ("代价红线", "有债必偿", "情感变量", "阈值", "羁绊抵押"):
        assert bad not in result.text


def test_question_filter_removes_model_invented_choice_menu():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门底层弟子，苟道藏锋")
    questions = ["前世记忆的代价形式更倾向消耗生命力还是削弱情感纽带？"]
    filtered = filter_stage_confirmation_questions("worldbuilding", questions, state)
    assert len(filtered) <= 1
    assert not any("消耗生命力" in q and "削弱情感纽带" in q for q in filtered)


def test_legacy_concept_stage_migrates_without_entering_active_flow():
    state = NovelState(project_id="demo", title="Demo", idea="旧项目")
    state.outline_stage = "concept"
    state.outline_stage_artifacts["concept"] = {
        "stage": "concept",
        "label": "故事概念",
        "status": "locked",
        "synthesis": "旧版故事概念。",
    }
    ensure_outline_stage(state)
    assert state.outline_stage in {"direction", "worldbuilding"}
    assert "concept" not in OUTLINE_STAGES


def test_persist_outputs_advances_current_stage_not_requested_next_stage(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.active_workflow = "outline"
    state.outline_stage = "direction"
    state.outline_stage_status = "options_ready"
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "options_ready",
        "synthesis": "## 方向定位稿\n- 类型定位：重生魔门苟道成长。",
        "pending_questions": [],
    }
    store.save_state(state)

    service = DirectorService(store, CodexCLIAdapter(mock=True), MockSearchBackend())
    decision = DirectorDecision(action="persist_outputs", task_args={"stage": "worldbuilding"})
    result = service._execute_decision(state, decision, "cli")

    assert result.state is not None
    assert result.state.outline_stage == "worldbuilding"
    assert result.state.outline_stage_artifacts["direction"]["status"] == "locked"
    assert result.state.outline_stage_artifacts["worldbuilding"]["status"] == "options_ready"
