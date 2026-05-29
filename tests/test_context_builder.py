from pathlib import Path

from ai_novelist.artifacts import save_markdown_artifact
from ai_novelist.bible import NovelBible, save_bible
from ai_novelist.context_builder import (
    ContextProfile,
    build_context,
    build_context_bundle,
    build_context_manifest,
    render_profile_sections,
    section_record,
)
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_drafting_context_includes_chapter_and_scene_cards(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "写第 1 章"
    save_markdown_artifact(store.project_dir("demo"), "chapters/chapter_001/chapter_card.md", "# 章节卡", "chapter_card", chapter=1)
    save_markdown_artifact(store.project_dir("demo"), "chapters/chapter_001/scene_cards.md", "# Scene 1", "scene_cards", chapter=1)

    context = build_context(state, store, "drafting", chapter=1)

    assert "# 章节卡" in context
    assert "# Scene 1" in context
    assert "写第 1 章" in context


def test_review_context_excludes_full_draft(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.chapter_draft = "# 草稿正文\n重复文本"
    save_markdown_artifact(store.project_dir("demo"), "chapters/chapter_001/draft_v1.md", "# 草稿正文", "chapter_draft", chapter=1)

    context = build_context(state, store, "review", chapter=1)

    assert "# 草稿正文" not in context


def test_locked_constraints_survive_truncation(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.locked_constraints = ["主角不能主动杀人", "结尾必须保留开放疑问"]
    bible = NovelBible()
    bible.project.title = "很长" * 500
    save_bible(store.project_dir("demo"), bible)

    context = build_context(state, store, "drafting", chapter=1, max_chars=260)

    assert "主角不能主动杀人" in context
    assert "结尾必须保留开放疑问" in context
    assert "已截断" in context


def test_max_chars_limit_applies(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.reference_brief = "参考" * 1000

    context = build_context(state, store, "outline_stage", max_chars=500)

    assert len(context) <= 520
    assert "# Task Context" in context


def test_context_includes_previous_chapter_summary(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.chapter_summaries = {"1": "主角发现第一条线索。", "2": "当前章摘要不应作为前文。"}

    context = build_context(state, store, "drafting", chapter=2)

    assert "主角发现第一条线索" in context
    assert "当前章摘要不应作为前文" not in context


def test_context_bundle_records_sources_and_respects_profile_limit(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "审稿第 1 章"
    state.locked_constraints = ["主角不能主动杀人"]
    state.current_chapter_card = "章节卡" * 1000

    bundle = build_context_bundle(state, store, "review_context", chapter=1)
    manifest = build_context_manifest(bundle)

    assert bundle.total_chars <= 9000
    assert bundle.estimated_tokens > 0
    assert any(item["section"] == "锁定约束" for item in manifest)
    assert all("included_chars" in item for item in manifest)


def test_context_manifest_records_artifact_path(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    save_markdown_artifact(
        store.project_dir("demo"),
        "chapters/chapter_001/chapter_card.md",
        "# 章节卡\n\n唯一章节卡内容",
        "chapter_card",
        chapter=1,
    )

    bundle = build_context_bundle(state, store, "drafting", chapter=1)
    manifest = build_context_manifest(bundle)

    assert any(item["path"] == "chapters/chapter_001/chapter_card.md" for item in manifest)
    assert any(item["source_type"] == "artifact:chapter_card" for item in manifest)


def test_context_deduplicates_artifact_and_state_fallback_by_digest(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter_card = "# 章节卡\n\n唯一重复内容"
    save_markdown_artifact(
        store.project_dir("demo"),
        "chapters/chapter_001/chapter_card.md",
        "# 章节卡\n\n唯一重复内容",
        "chapter_card",
        chapter=1,
    )

    bundle = build_context_bundle(state, store, "drafting", chapter=1)

    assert bundle.text.count("唯一重复内容") == 1
    assert len({item.digest for item in bundle.sources if item.digest}) == len([item for item in bundle.sources if item.digest])


def test_context_dedupe_keeps_all_duplicate_protected_sections():
    profile = ContextProfile(name="test_profile", purpose="test", max_chars=2000, sections=())
    sections = [
        ("用户当前请求", "重复保护内容"),
        ("当前任务", "重复保护内容"),
        ("锁定约束", "重复保护内容"),
    ]

    text, sources = render_profile_sections(sections, profile, max_chars=2000)

    assert "## 用户当前请求" in text
    assert "## 当前任务" in text
    assert "## 锁定约束" in text
    assert text.count("重复保护内容") == 3
    assert [source.section for source in sources] == ["用户当前请求", "当前任务", "锁定约束"]


def test_context_dedupe_keeps_protected_section_over_duplicate_artifact():
    profile = ContextProfile(name="test_profile", purpose="test", max_chars=2000, sections=())
    sections = [
        ("锁定约束", "共享内容"),
        section_record(
            "当前任务 Artifact: chapter_card",
            "共享内容",
            source_type="artifact:chapter_card",
            path="chapters/chapter_001/chapter_card.md",
            priority=10,
        ),
    ]

    text, sources = render_profile_sections(sections, profile, max_chars=2000)

    assert "## 锁定约束" in text
    assert "## 当前任务 Artifact: chapter_card" not in text
    assert [source.section for source in sources] == ["锁定约束"]
    assert all(source.source_type != "artifact:chapter_card" for source in sources)


def test_context_dedupe_preserves_original_order_after_priority_selection():
    profile = ContextProfile(name="test_profile", purpose="test", max_chars=2000, sections=())
    sections = [
        section_record("第一节", "第一节内容", source_type="state:first", priority=80),
        section_record("较早重复节", "重复内容", source_type="state:duplicate", priority=80),
        section_record("中间节", "中间内容", source_type="state:middle", priority=50),
        section_record("优先重复节", "重复内容", source_type="artifact:chapter_card", path="chapter_card.md", priority=10),
    ]

    _, sources = render_profile_sections(sections, profile, max_chars=2000)

    assert [source.section for source in sources] == ["第一节", "中间节", "优先重复节"]


def test_context_cap_keeps_protected_sections_with_long_earlier_protected_content(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "很长用户请求" * 300
    state.locked_constraints = ["必须保留锁定约束"]

    bundle = build_context_bundle(state, store, "drafting", chapter=1, max_chars=360)

    assert "## 用户当前请求" in bundle.text
    assert "## 当前任务" in bundle.text
    assert "## 锁定约束" in bundle.text
    assert "必须保留锁定约束" in bundle.text
    assert "已截断" in bundle.text
    request_content = bundle.text.split("## 用户当前请求\n", 1)[1].split("\n\n## 当前任务", 1)[0]
    task_content = bundle.text.split("## 当前任务\n", 1)[1].split("\n\n## 锁定约束", 1)[0]
    constraints_content = bundle.text.split("## 锁定约束\n", 1)[1].split("\n\n", 1)[0]
    assert request_content.strip()
    assert task_content.strip()
    assert constraints_content.strip()
    manifest_by_section = {source.section: source for source in bundle.sources}
    assert manifest_by_section["用户当前请求"].truncated is True
    assert manifest_by_section["用户当前请求"].included_chars == len(request_content)
    assert manifest_by_section["当前任务"].included_chars == len(task_content)
    assert manifest_by_section["锁定约束"].included_chars == len(constraints_content.rstrip())


def test_bible_update_context_uses_protected_renderer_under_cap(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "很长圣经更新请求" * 300
    state.locked_constraints = ["必须保留圣经约束"]

    context = build_context(state, store, "bible_update", max_chars=260)

    assert "## 用户当前请求" in context
    assert "## 当前任务" in context
    assert "## 锁定约束" in context
    assert "bible_update" in context
    assert "必须保留圣经约束" in context
    assert "已截断" in context


def test_context_bundle_marks_dropped_unprotected_sections_as_truncated(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "短请求"
    state.locked_constraints = ["短约束"]
    state.current_chapter_card = "巨大章节卡" * 500

    bundle = build_context_bundle(state, store, "drafting", chapter=1, max_chars=180)

    assert "巨大章节卡" not in bundle.text
    assert bundle.truncated is True
    assert any(source.truncated or source.included_chars == 0 for source in bundle.sources)
    assert any(source.section == "当前任务 Artifact: current_chapter_card" and source.included_chars == 0 for source in bundle.sources)


def test_chapter_planning_context_uses_chapter_outline_slice(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter = 2
    state.active_chapter = 2
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "label": "章节大纲",
        "synthesis": """## 章节大纲稿

### 第一卷：入局卷

#### 第 1 章：开局
- 第一章专属内容。

#### 第 2 章：冲突
- 第二章专属内容。

#### 第 3 章：反转
- 第三章专属内容。
""",
    }
    store.save_state(state)

    context = build_context(state, store, "chapter_planning", chapter=2)

    assert "第二章专属内容" in context
    assert "第一章专属内容" not in context
    assert "第三章专属内容" not in context


def test_direct_chapter_context_profile_uses_selected_outline_and_manifest(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "写第 2 章"
    state.active_chapter = 2
    state.current_chapter = 2
    state.director_task_args["selected_chapter_outline"] = "第 2 章专属大纲"
    state.chapter_summaries = {"1": "第一章摘要", "2": "当前章摘要不应注入"}

    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=2)
    manifest = build_context_manifest(bundle)

    assert "第 2 章专属大纲" in bundle.text
    assert "第一章摘要" in bundle.text
    assert "当前章摘要不应注入" not in bundle.text
    assert any(item["section"] == "章节大纲切片" for item in manifest)


def test_direct_chapter_context_manifest_marks_fallback_outline(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 7
    state.active_chapter = 7
    outline = """## 第一卷

### 第 6 章：只给第六章
第六章相邻大纲内容。

### 第 8 章：只给第八章
第八章相邻大纲内容。
"""
    save_markdown_artifact(
        store.project_dir(state.project_id),
        "outline/chapter_outline.md",
        outline,
        "chapter_outline",
        stage="chapter_outline",
    )
    store.save_state(state)

    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=7)
    manifest = build_context_manifest(bundle)

    assert any(item["section"] == "章节大纲切片" for item in manifest)
    assert any(item["source_type"] == "chapter_outline_slice" for item in manifest)
    assert "章节大纲切片缺失" in bundle.text
    assert "只给第六章" not in bundle.text
    assert "第六章相邻大纲内容" not in bundle.text
    assert "只给第八章" not in bundle.text
    assert "第八章相邻大纲内容" not in bundle.text


def test_direct_chapter_context_missing_chinese_number_outline_slice_does_not_leak_adjacent_chapters(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 7
    state.active_chapter = 7
    outline = """## 第一卷

### 第六章：只给第六章
第六章中文相邻大纲内容。

### 第八章：只给第八章
第八章中文相邻大纲内容。
"""
    save_markdown_artifact(
        store.project_dir(state.project_id),
        "outline/chapter_outline.md",
        outline,
        "chapter_outline",
        stage="chapter_outline",
    )
    store.save_state(state)

    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=7)

    assert "章节大纲切片缺失" in bundle.text
    assert "只给第六章" not in bundle.text
    assert "第六章中文相邻大纲内容" not in bundle.text
    assert "只给第八章" not in bundle.text
    assert "第八章中文相邻大纲内容" not in bundle.text


def test_direct_chapter_context_uses_present_chinese_number_outline_slice(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 7
    state.active_chapter = 7
    outline = """## 第一卷

### 第六章：只给第六章
第六章中文相邻大纲内容。

### 第七章：只给第七章
第七章中文专属大纲内容。

### 第八章：只给第八章
第八章中文相邻大纲内容。
"""
    save_markdown_artifact(
        store.project_dir(state.project_id),
        "outline/chapter_outline.md",
        outline,
        "chapter_outline",
        stage="chapter_outline",
    )
    store.save_state(state)

    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=7)

    assert "只给第七章" in bundle.text
    assert "第七章中文专属大纲内容" in bundle.text
    assert "只给第六章" not in bundle.text
    assert "第六章中文相邻大纲内容" not in bundle.text
    assert "只给第八章" not in bundle.text
    assert "第八章中文相邻大纲内容" not in bundle.text
