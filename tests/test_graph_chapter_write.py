from pathlib import Path

from ai_novelist.graph_chapter_write import load_direct_write_context_node
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def test_direct_chapter_load_context_missing_outline_slice_does_not_leak_adjacent_chapters(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 7
    state.active_chapter = 7
    state.director_task_args = {"chapter": 7}
    outline = """## 第一卷

### 第 6 章：只给第六章
第六章相邻大纲内容。

### 第 8 章：只给第八章
第八章相邻大纲内容。
"""
    store.save_outline_artifact(state, "chapter_outline", outline)
    store.save_state(state)

    result = NovelState.from_dict(load_direct_write_context_node(state.to_dict(), store))
    selected_outline = result.director_task_args["selected_chapter_outline"]
    context = result.director_task_args["direct_chapter_context"]

    assert "章节大纲切片缺失" in selected_outline
    assert "章节大纲切片缺失" in context
    assert "只给第六章" not in selected_outline
    assert "第六章相邻大纲内容" not in selected_outline
    assert "只给第八章" not in selected_outline
    assert "第八章相邻大纲内容" not in selected_outline
    assert "只给第六章" not in context
    assert "第六章相邻大纲内容" not in context
    assert "只给第八章" not in context
    assert "第八章相邻大纲内容" not in context


def test_direct_chapter_load_context_uses_present_chapter_outline_slice(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 2
    state.active_chapter = 2
    state.director_task_args = {"chapter": 2}
    outline = """## 第一卷

### 第 1 章：只给第一章
第一章相邻大纲内容。

### 第 2 章：只给第二章
第二章专属大纲内容。

### 第 3 章：只给第三章
第三章相邻大纲内容。
"""
    store.save_outline_artifact(state, "chapter_outline", outline)
    store.save_state(state)

    result = NovelState.from_dict(load_direct_write_context_node(state.to_dict(), store))
    selected_outline = result.director_task_args["selected_chapter_outline"]
    context = result.director_task_args["direct_chapter_context"]

    assert "只给第二章" in selected_outline
    assert "第二章专属大纲内容" in selected_outline
    assert "只给第二章" in context
    assert "第二章专属大纲内容" in context
    assert "只给第一章" not in selected_outline
    assert "第一章相邻大纲内容" not in selected_outline
    assert "只给第三章" not in selected_outline
    assert "第三章相邻大纲内容" not in selected_outline


def test_direct_chapter_load_context_missing_chinese_number_outline_slice_does_not_leak_adjacent_chapters(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 7
    state.active_chapter = 7
    state.director_task_args = {"chapter": 7}
    outline = """## 第一卷

### 第六章：只给第六章
第六章中文相邻大纲内容。

### 第八章：只给第八章
第八章中文相邻大纲内容。
"""
    store.save_outline_artifact(state, "chapter_outline", outline)
    store.save_state(state)

    result = NovelState.from_dict(load_direct_write_context_node(state.to_dict(), store))
    selected_outline = result.director_task_args["selected_chapter_outline"]
    context = result.director_task_args["direct_chapter_context"]

    assert "章节大纲切片缺失" in selected_outline
    assert "章节大纲切片缺失" in context
    assert "只给第六章" not in selected_outline
    assert "第六章中文相邻大纲内容" not in selected_outline
    assert "只给第八章" not in selected_outline
    assert "第八章中文相邻大纲内容" not in selected_outline
    assert "只给第六章" not in context
    assert "第六章中文相邻大纲内容" not in context
    assert "只给第八章" not in context
    assert "第八章中文相邻大纲内容" not in context


def test_direct_chapter_load_context_uses_present_chinese_number_outline_slice(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 7
    state.active_chapter = 7
    state.director_task_args = {"chapter": 7}
    outline = """## 第一卷

### 第六章：只给第六章
第六章中文相邻大纲内容。

### 第七章：只给第七章
第七章中文专属大纲内容。

### 第八章：只给第八章
第八章中文相邻大纲内容。
"""
    store.save_outline_artifact(state, "chapter_outline", outline)
    store.save_state(state)

    result = NovelState.from_dict(load_direct_write_context_node(state.to_dict(), store))
    selected_outline = result.director_task_args["selected_chapter_outline"]
    context = result.director_task_args["direct_chapter_context"]

    assert "只给第七章" in selected_outline
    assert "第七章中文专属大纲内容" in selected_outline
    assert "只给第七章" in context
    assert "第七章中文专属大纲内容" in context
    assert "只给第六章" not in selected_outline
    assert "第六章中文相邻大纲内容" not in selected_outline
    assert "只给第八章" not in selected_outline
    assert "第八章中文相邻大纲内容" not in selected_outline
