"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.adapters.deepseek import DeepSeekAdapter
from ai_novelist.artifacts import save_json_artifact
from ai_novelist.config import Settings, load_settings, search_api_key
from ai_novelist.corpus.craft_extractor import extract_craft_profiles
from ai_novelist.corpus.craft_resolver import resolve_author_craft
from ai_novelist.corpus.index import build_corpus_index, load_chunks, load_profiles
from ai_novelist.corpus.similarity_guard import check_similarity
from ai_novelist.director_service import DirectorService
from ai_novelist.feishu import FeishuBotService, FeishuConfigError, run_feishu_long_connection
from ai_novelist.graph_minimal import build_minimal_graph
from ai_novelist.graph_outline import build_outline_collaboration_graph
from ai_novelist.graph_research import build_research_graph, detect_research_need_text
from ai_novelist.research import (
    LocalFirstSearchBackend,
    LocalRAGSearchBackend,
    MockSearchBackend,
    SearchBackend,
    SearchBackendError,
    WebSearchBackend,
)
from ai_novelist.graph_writer import (
    AgentTask,
    append_message,
    artifact_status,
    build_chat_graph,
    build_director_prompt,
    build_reference_summary,
    build_composer_graph,
    build_writer_graph,
    parse_director_decision,
    task_display_name,
    task_output,
)
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = load_settings()
    store = LocalStore(settings.projects_dir)

    try:
        if args.command == "init":
            return init_project(args, store)
        if args.command == "outline":
            return generate_project_outline(args, store, settings)
        if args.command == "compose":
            return run_compose_command(args, store, settings)
        if args.command == "chat":
            return run_chat_command(args, store, settings)
        if args.command == "feishu":
            return run_feishu_command(args, store, settings)
        if args.command == "index-corpus":
            return run_index_corpus_command(args, settings)
        if args.command == "extract-craft":
            return run_extract_craft_command(args, settings)
        if args.command == "craft-status":
            return run_craft_status_command(args, store, settings)
        if args.command == "craft-profiles":
            return run_craft_profiles_command(args, settings)
        if args.command == "craft-brief":
            return run_craft_brief_command(args, store, settings)
        if args.command == "craft-similarity-check":
            return run_craft_similarity_check_command(args, store, settings)
        if args.command == "plan-outline":
            return run_writer_command(args, store, settings, "plan_outline")
        if args.command == "plan-chapters":
            return run_writer_command(args, store, settings, "plan_chapters")
        if args.command == "write-chapter":
            return run_writer_command(args, store, settings, "write_chapter")
        if args.command == "review":
            return run_writer_command(args, store, settings, "review")
        if args.command == "finalize-chapter":
            return run_finalize_command(args, store, settings)
        if args.command == "export":
            return run_export_command(args, store)
        if args.command == "show":
            return show_project(args, store)
    except (LocalStoreError, SearchBackendError, FeishuConfigError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-novelist")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="创建小说项目")
    init_parser.add_argument("--title", required=True, help="小说标题")
    init_parser.add_argument("--project", help="项目 ID，默认由标题生成")

    outline_parser = subparsers.add_parser("outline", help="生成小说大纲")
    outline_parser.add_argument("--project", required=True, help="项目 ID")
    outline_parser.add_argument("--idea", required=True, help="小说创意")
    add_generation_flags(outline_parser)

    compose_parser = subparsers.add_parser("compose", help="运行阶段 2 多 Agent 完整创作流程")
    compose_parser.add_argument("--project", required=True, help="项目 ID；不存在时会自动创建")
    compose_parser.add_argument("--idea", required=True, help="小说创意")
    compose_parser.add_argument("--chapter", type=int, default=1, help="章节编号，从 1 开始")
    compose_parser.add_argument("--max-revisions", type=int, default=1, help="编辑要求修改时最多自动重写次数")
    add_generation_flags(compose_parser)

    chat_parser = subparsers.add_parser("chat", help="进入 Director Agent 连续对话模式")
    chat_parser.add_argument("--project", required=True, help="项目 ID；不存在时会自动创建")
    chat_parser.add_argument("--mock", action="store_true", help="使用本地 mock 输出，不调用真实模型")
    chat_parser.add_argument("--timeout", type=int, help="真实模型调用超时时间，单位秒")
    chat_parser.add_argument("--provider", choices=("codex", "deepseek"), help="模型提供方，默认读 AI_NOVELIST_MODEL_PROVIDER")
    chat_parser.add_argument("--model", help="模型名；DeepSeek 默认 deepseek-v4-pro")
    chat_parser.add_argument(
        "--local-corpus-dir",
        help="本地 RAG 语料目录，默认读 AI_NOVELIST_LOCAL_CORPUS_DIR；配置后 research 优先检索 .txt/.md",
    )
    chat_parser.add_argument(
        "--search-provider",
        choices=("mock", "serpapi", "tavily", "exa"),
        help="搜索提供方，默认读 AI_NOVELIST_SEARCH_PROVIDER；--mock 会强制使用 mock",
    )
    add_author_craft_flags(chat_parser)

    feishu_parser = subparsers.add_parser("feishu", help="启动飞书长连接机器人")
    feishu_parser.add_argument("--mock", action="store_true", help="使用本地 mock 输出，不调用真实模型")
    feishu_parser.add_argument("--timeout", type=int, help="真实模型调用超时时间，单位秒")
    feishu_parser.add_argument("--provider", choices=("codex", "deepseek"), help="模型提供方，默认读 AI_NOVELIST_MODEL_PROVIDER")
    feishu_parser.add_argument("--model", help="模型名；DeepSeek 默认 deepseek-v4-pro")
    feishu_parser.add_argument(
        "--local-corpus-dir",
        help="本地 RAG 语料目录，默认读 AI_NOVELIST_LOCAL_CORPUS_DIR；配置后 research 优先检索 .txt/.md",
    )
    feishu_parser.add_argument(
        "--search-provider",
        choices=("mock", "serpapi", "tavily", "exa"),
        help="搜索提供方，默认读 AI_NOVELIST_SEARCH_PROVIDER；--mock 会强制使用 mock",
    )
    add_author_craft_flags(feishu_parser)

    index_parser = subparsers.add_parser("index-corpus", help="索引本地作者小说语料")
    index_parser.add_argument("--corpus-dir", help="本地小说语料目录，默认读 AI_NOVELIST_AUTHOR_CORPUS_DIR")
    index_parser.add_argument("--index-dir", help="索引输出目录，默认读 AI_NOVELIST_CORPUS_INDEX_DIR")
    index_parser.add_argument("--no-incremental", action="store_true", help="重新扫描全部文件")

    extract_parser = subparsers.add_parser("extract-craft", help="从 corpus index 提炼作者构思方法")
    extract_parser.add_argument("--index-dir", help="索引目录，默认读 AI_NOVELIST_CORPUS_INDEX_DIR")
    extract_parser.add_argument("--mock", action="store_true", help="使用稳定规则提炼，不调用真实模型")
    extract_parser.add_argument("--timeout", type=int, help="真实模型调用超时时间，单位秒")
    extract_parser.add_argument("--provider", choices=("codex", "deepseek"), help="模型提供方，默认读 AI_NOVELIST_MODEL_PROVIDER")
    extract_parser.add_argument("--model", help="模型名；DeepSeek 默认 deepseek-v4-pro")
    extract_parser.add_argument("--limit-files", type=int, help="最多处理多少本作品")
    extract_parser.add_argument("--limit-chunks", type=int, help="最多处理多少 chunk")
    extract_parser.add_argument("--work-id", default="", help="只处理指定 work_id")
    extract_parser.add_argument("--dry-run", action="store_true", help="只统计，不写 profile")
    extract_parser.add_argument("--resume", action="store_true", help="保留已完成 profile 并继续")

    craft_status_parser = subparsers.add_parser("craft-status", help="查看项目 Author Craft 状态")
    craft_status_parser.add_argument("--project", required=True, help="项目 ID")
    craft_status_parser.add_argument("--index-dir", help="索引目录，默认读 AI_NOVELIST_CORPUS_INDEX_DIR")

    profiles_parser = subparsers.add_parser("craft-profiles", help="列出已提炼的 craft profiles")
    profiles_parser.add_argument("--index-dir", help="索引目录，默认读 AI_NOVELIST_CORPUS_INDEX_DIR")
    profiles_parser.add_argument("--limit", type=int, default=20, help="最多显示多少个 profile")

    brief_parser = subparsers.add_parser("craft-brief", help="为指定阶段生成 StageCraftBrief")
    brief_parser.add_argument("--project", required=True, help="项目 ID")
    brief_parser.add_argument("--purpose", required=True, choices=("outline_stage", "chapter_planning", "scene_design", "drafting", "review", "revision"), help="阶段 purpose")
    brief_parser.add_argument("--chapter", type=int, help="章节编号")
    brief_parser.add_argument("--stage", help="大纲阶段名")
    brief_parser.add_argument("--mock", action="store_true", help="兼容参数；brief 生成不调用模型")
    add_author_craft_flags(brief_parser)

    similarity_parser = subparsers.add_parser("craft-similarity-check", help="检查文本与 Author Craft 语料的相似风险")
    similarity_parser.add_argument("--project", required=True, help="项目 ID")
    similarity_parser.add_argument("--chapter", type=int, required=True, help="章节编号")
    similarity_parser.add_argument("--draft", required=True, help="要检查的草稿路径")
    add_author_craft_flags(similarity_parser)

    outline_plan_parser = subparsers.add_parser("plan-outline", help="生成或重整总大纲")
    outline_plan_parser.add_argument("--project", required=True, help="项目 ID")
    add_generation_flags(outline_plan_parser)

    plan_parser = subparsers.add_parser("plan-chapters", help="生成章节细纲")
    plan_parser.add_argument("--project", required=True, help="项目 ID")
    add_generation_flags(plan_parser)

    write_parser = subparsers.add_parser("write-chapter", help="生成指定章节正文")
    write_parser.add_argument("--project", required=True, help="项目 ID")
    write_parser.add_argument("--chapter", type=int, required=True, help="章节编号，从 1 开始")
    add_generation_flags(write_parser)

    review_parser = subparsers.add_parser("review", help="生成编辑审稿意见")
    review_parser.add_argument("--project", required=True, help="项目 ID")
    review_parser.add_argument("--chapter", type=int, help="章节编号，默认使用当前章节")
    add_generation_flags(review_parser)

    finalize_parser = subparsers.add_parser("finalize-chapter", help="定稿指定章节并更新小说圣经")
    finalize_parser.add_argument("--project", required=True, help="项目 ID")
    finalize_parser.add_argument("--chapter", type=int, required=True, help="章节编号，从 1 开始")
    add_generation_flags(finalize_parser)

    export_parser = subparsers.add_parser("export", help="导出已定稿小说")
    export_parser.add_argument("--project", required=True, help="项目 ID")

    show_parser = subparsers.add_parser("show", help="显示项目状态")
    show_parser.add_argument("--project", required=True, help="项目 ID")

    return parser


def add_generation_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mock", action="store_true", help="使用本地 mock 输出，不调用真实模型")
    parser.add_argument("--auto-approve", action="store_true", help="跳过人工输入并自动确认")
    parser.add_argument("--timeout", type=int, help="真实模型调用超时时间，单位秒")
    parser.add_argument("--provider", choices=("codex", "deepseek"), help="模型提供方，默认读 AI_NOVELIST_MODEL_PROVIDER")
    parser.add_argument("--model", help="模型名；DeepSeek 默认 deepseek-v4-pro")
    add_author_craft_flags(parser)


def add_author_craft_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--author-corpus-dir", help="本地作者小说语料目录，默认读 AI_NOVELIST_AUTHOR_CORPUS_DIR")
    parser.add_argument("--corpus-index-dir", help="Author Craft 索引目录，默认读 AI_NOVELIST_CORPUS_INDEX_DIR")
    parser.add_argument("--craft-mode", choices=("off", "assist", "strict"), help="Author Craft 使用模式")
    parser.add_argument("--craft-max-chars", type=int, help="StageCraftBrief 最大字符数")
    parser.add_argument("--craft-profile", action="append", default=[], help="限定 craft profile id，可重复")
    parser.add_argument("--craft-genre", action="append", default=[], help="优先参考的类型标签，可重复")
    parser.add_argument("--craft-exclude-work", action="append", default=[], help="排除指定 work_id，可重复")


def init_project(args: argparse.Namespace, store: LocalStore) -> int:
    state = store.create_project(args.title, args.project)
    print(f"项目已创建：{state.project_id}")
    print(f"目录：{store.project_dir(state.project_id)}")
    return 0


def run_index_corpus_command(args: argparse.Namespace, settings: Settings) -> int:
    corpus_dir = args.corpus_dir or settings.author_corpus_dir
    if not corpus_dir:
        print("错误：请通过 --corpus-dir 或 AI_NOVELIST_AUTHOR_CORPUS_DIR 指定语料目录", file=sys.stderr)
        return 2
    index_dir = args.index_dir or settings.corpus_index_dir
    result = build_corpus_index(corpus_dir, index_dir, incremental=not args.no_incremental)
    print(f"索引目录：{result.index_dir}")
    print(f"作品：{result.works}，章节：{result.chapters}，场景：{result.scenes}，chunks：{result.chunks}")
    print(f"未变化文件：{result.skipped_files}，错误：{result.errors}")
    return 0 if result.errors == 0 else 1


def run_extract_craft_command(args: argparse.Namespace, settings: Settings) -> int:
    index_dir = args.index_dir or settings.corpus_index_dir
    result = extract_craft_profiles(
        index_dir,
        mock=args.mock or settings.craft_extract_mock,
        limit_files=args.limit_files,
        limit_chunks=args.limit_chunks,
        work_id=args.work_id,
        dry_run=args.dry_run,
        resume=args.resume,
    )
    prefix = "Dry run" if result.dry_run else "已提炼"
    print(f"{prefix}：work={result.work_profiles}, chapter={result.chapter_profiles}, scene={result.scene_profiles}, genre={result.genre_profiles}")
    print(f"索引目录：{result.index_dir}")
    return 0


def run_craft_status_command(args: argparse.Namespace, store: LocalStore, settings: Settings) -> int:
    state = store.load_state(args.project)
    index_dir = Path(args.index_dir or settings.corpus_index_dir)
    print(f"项目：{state.project_id}")
    print(f"craft_mode：{state.craft_mode}")
    print(f"index_dir：{index_dir}")
    print(f"active_craft_brief_path：{state.active_craft_brief_path or '暂无'}")
    print(f"craft_context_digest：{state.craft_context_digest or '暂无'}")
    memory_path = store.project_craft_memory_path(state.project_id)
    print(f"project_craft_memory：{'已有' if memory_path.exists() else '暂无'} -> {memory_path}")
    return 0


def run_craft_profiles_command(args: argparse.Namespace, settings: Settings) -> int:
    index_dir = Path(args.index_dir or settings.corpus_index_dir)
    count = 0
    for profile in load_profiles(index_dir):
        print(f"{profile.profile_id}\t{profile.scope}\t{profile.work_id}\t{profile.title}\tnotes={len(profile.notes)}")
        count += 1
        if count >= args.limit:
            break
    if count == 0:
        print("暂无 craft profiles。请先运行 index-corpus 和 extract-craft。")
    return 0


def run_craft_brief_command(args: argparse.Namespace, store: LocalStore, settings: Settings) -> int:
    try:
        state = store.load_state(args.project)
    except LocalStoreError:
        state = store.create_project(args.project, args.project)
    if args.chapter:
        state.current_chapter = args.chapter
        state.active_chapter = args.chapter
    apply_craft_args_to_state(state, args, settings)
    if state.craft_mode == "off":
        state.craft_mode = "assist"
    state = resolve_author_craft(state, store, args.purpose, chapter=args.chapter, stage=args.stage, max_chars=state.craft_options.get("craft_max_chars"))
    store.save_state(state)
    if not state.active_craft_brief_path:
        print("未生成 StageCraftBrief。请确认 index-dir 下已有 craft profiles。", file=sys.stderr)
        return 1
    path = store.project_dir(state.project_id) / state.active_craft_brief_path
    print(f"StageCraftBrief：{path}")
    print(path.read_text(encoding="utf-8"))
    return 0


def run_craft_similarity_check_command(args: argparse.Namespace, store: LocalStore, settings: Settings) -> int:
    state = store.load_state(args.project)
    apply_craft_args_to_state(state, args, settings)
    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"错误：草稿不存在：{draft_path}", file=sys.stderr)
        return 2
    index_dir = Path(state.craft_options.get("corpus_index_dir") or settings.corpus_index_dir)
    chunks = list(load_chunks(index_dir))[:100]
    report = check_similarity(
        draft_path.read_text(encoding="utf-8"),
        chunks,
        artifact=draft_path.stem,
        project_id=state.project_id,
        chapter=args.chapter,
    )
    relative_path = store.craft_similarity_report_relative_path(args.chapter, draft_path.stem)
    record = save_json_artifact(
        store.project_dir(state.project_id),
        relative_path,
        report.to_dict(),
        "craft_similarity_report",
        chapter=args.chapter,
        stage=draft_path.stem,
        source_agent="similarity_guard",
        graph="cli",
        summary=f"risk={report.risk}",
    )
    output_path = store.project_dir(state.project_id) / record.path
    print(f"risk：{report.risk}")
    print(f"报告：{output_path}")
    return 1 if report.risk == "high" else 0


def apply_craft_args_to_state(state: NovelState, args: argparse.Namespace, settings: Settings) -> None:
    mode = getattr(args, "craft_mode", None) or settings.craft_mode or "off"
    state.craft_mode = mode if mode in {"off", "assist", "strict"} else "off"
    options = dict(state.craft_options or {})
    if getattr(args, "author_corpus_dir", None) or settings.author_corpus_dir:
        options["author_corpus_dir"] = getattr(args, "author_corpus_dir", None) or settings.author_corpus_dir
    if getattr(args, "corpus_index_dir", None) or settings.corpus_index_dir:
        options["corpus_index_dir"] = getattr(args, "corpus_index_dir", None) or settings.corpus_index_dir
    options["craft_mode"] = state.craft_mode
    options["craft_max_chars"] = getattr(args, "craft_max_chars", None) or settings.craft_max_chars
    if getattr(args, "craft_profile", None):
        options["craft_profile"] = list(args.craft_profile)
    if getattr(args, "craft_genre", None):
        options["craft_genre"] = list(args.craft_genre)
    if getattr(args, "craft_exclude_work", None):
        options["craft_exclude_work"] = list(args.craft_exclude_work)
    state.craft_options = options


def craft_options_from_args(args: argparse.Namespace, settings: Settings) -> dict:
    dummy = NovelState(project_id="_", title="_")
    apply_craft_args_to_state(dummy, args, settings)
    return dict(dummy.craft_options)


def generate_project_outline(
    args: argparse.Namespace,
    store: LocalStore,
    settings: Settings,
) -> int:
    try:
        state = store.load_state(args.project)
    except LocalStoreError:
        state = store.create_project(args.project, args.project)
    state.idea = args.idea
    state.user_request = "请基于这个创意生成大纲"
    state.last_user_feedback = state.user_request
    state.review_status = "draft"
    state.error = ""
    apply_craft_args_to_state(state, args, settings)
    append_message(state, "user", state.user_request)
    store.save_state(state)

    effective_timeout = args.timeout if args.timeout is not None else settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    graph = build_outline_collaboration_graph(adapter, store, progress=print_progress)
    result = NovelState.from_dict(graph.invoke(state.to_dict()))
    print_outline_turn_result(result, store)

    if result.error:
        print(f"错误：{result.error}", file=sys.stderr)
        return 1

    if args.auto_approve:
        result.user_request = "保存大纲"
        result.last_user_feedback = result.user_request
        append_message(result, "user", result.user_request)
        store.save_state(result)
        result = NovelState.from_dict(graph.invoke(result.to_dict()))
        print_outline_turn_result(result, store)
        return 0 if result.review_status == "approved" else 1

    print("\n进入大纲共创模式。可输入 approve / revise: ... / variant / review / lock: ... / stop。")
    while True:
        try:
            user_input = input("outline> ").strip()
        except EOFError:
            print()
            break
        if not user_input:
            continue
        normalized = normalize_outline_feedback(user_input)
        result.user_request = normalized
        result.last_user_feedback = normalized
        append_message(result, "user", normalized)
        store.save_state(result)
        result = NovelState.from_dict(graph.invoke(result.to_dict()))
        print_outline_turn_result(result, store)
        if result.error:
            print(f"错误：{result.error}", file=sys.stderr)
            return 1
        if result.review_status == "approved" or result.director_action == "stop" or normalized in {"stop", "退出", "结束"}:
            break
    return 0


def normalize_outline_feedback(text: str) -> str:
    lowered = text.strip().lower()
    if lowered in {"approve", "approved", "yes", "y", "确认", "通过"}:
        return "保存大纲"
    if lowered in {"variant", "variants", "方向", "备选"}:
        return "给我三个不同方向"
    if lowered in {"review", "审查", "审稿"}:
        return "审查大纲"
    if lowered in {"stop", "exit", "quit", "退出", "结束"}:
        return "stop"
    if lowered.startswith("revise:") or lowered.startswith("revise："):
        return "修改大纲：" + text.split(":", 1)[-1].split("：", 1)[-1].strip()
    if lowered.startswith("lock:") or lowered.startswith("lock："):
        return "这个设定别改：" + text.split(":", 1)[-1].split("：", 1)[-1].strip()
    return text


def print_outline_turn_result(state: NovelState, store: LocalStore) -> None:
    if state.director_message:
        print(f"Director> {state.director_message}")
    print(f"审核状态：{state.review_status}")
    if state.editor_decision != "unknown":
        print(f"大纲编辑结论：{state.editor_decision}，质量分：{state.quality_score}")
    print_outline_artifacts(state)
    if state.style_preferences:
        print("风格偏好：" + "，".join(state.style_preferences))
    if state.review_status == "approved":
        print(f"大纲已保存：{store.outline_path(state.project_id)}")


def run_compose_command(
    args: argparse.Namespace,
    store: LocalStore,
    settings: Settings,
) -> int:
    if args.chapter < 1:
        print("错误：章节编号必须大于 0", file=sys.stderr)
        return 2
    if args.max_revisions < 0:
        print("错误：最大修订次数不能小于 0", file=sys.stderr)
        return 2

    try:
        state = store.load_state(args.project)
    except LocalStoreError:
        state = store.create_project(args.project, args.project)

    state.idea = args.idea
    state.current_chapter = args.chapter
    state.max_revisions = args.max_revisions
    state.revision_count = 0
    state.editor_decision = "unknown"
    state.quality_score = 0
    state.next_action = "continue"
    state.review_status = "draft"
    state.error = ""
    apply_craft_args_to_state(state, args, settings)
    store.save_state(state)

    effective_timeout = args.timeout if args.timeout is not None else settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    if not state.outline.strip() or not store.outline_path(state.project_id).exists():
        state.user_request = "请启动或继续阶段化大纲共创"
        state.active_workflow = "outline"
        append_message(state, "user", state.user_request)
        store.save_state(state)
        graph = build_outline_collaboration_graph(adapter, store, progress=print_progress)
        result = NovelState.from_dict(graph.invoke(state.to_dict()))
        print_outline_turn_result(result, store)
        if args.auto_approve and result.outline_stage_status == "options_ready" and result.outline_stage != "done":
            result.user_request = "确认进入下一阶段"
            append_message(result, "user", result.user_request)
            store.save_state(result)
            result = NovelState.from_dict(graph.invoke(result.to_dict()))
            print_outline_turn_result(result, store)
        return 1 if result.error else 0

    graph = build_composer_graph(adapter, store, review_func=make_compose_review_func(args.auto_approve))
    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    if result.error:
        print(f"错误：{result.error}", file=sys.stderr)
    print(f"审核状态：{result.review_status}")
    print(f"编辑结论：{result.editor_decision}")
    print(f"质量分：{result.quality_score}")
    print(f"修订次数：{result.revision_count}")
    if result.review_status == "approved":
        print_compose_paths(result, store)
        return 0
    return 1 if result.review_status in {"error", "stopped"} else 0


def run_chat_command(
    args: argparse.Namespace,
    store: LocalStore,
    settings: Settings,
) -> int:
    try:
        state = store.load_state(args.project)
    except LocalStoreError:
        state = store.create_project(args.project, args.project)
    apply_craft_args_to_state(state, args, settings)
    store.save_state(state)

    effective_timeout = args.timeout if args.timeout is not None else settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    service = DirectorService(
        store=store,
        adapter=adapter,
        search_backend=make_search_backend(args, settings),
        progress=print_progress,
        default_craft_mode=getattr(args, "craft_mode", None) or settings.craft_mode,
        default_craft_options=craft_options_from_args(args, settings),
    )

    print(f"进入 ai-novelist chat：项目 {state.project_id}。输入 exit/quit/退出 结束。")
    print_project_startup_context(state, store)
    while True:
        try:
            user_input = input("你> ").strip()
        except EOFError:
            print()
            break
        if not user_input:
            continue

        turn = service.handle_turn(args.project, user_input, channel="cli")
        if turn.immediate_message:
            print(f"Director> {turn.immediate_message}")
            print_turn_choices(turn.choices)
        elif turn.state is not None:
            print_chat_turn_result(turn.state, store)
        elif turn.final_message:
            print(f"Director> {turn.final_message}")
        if turn.state and turn.state.error:
            print(f"错误：{turn.state.error}", file=sys.stderr)
            return 1
        if turn.state and turn.state.director_action == "stop":
            break
    return 0


def run_feishu_command(
    args: argparse.Namespace,
    store: LocalStore,
    settings: Settings,
) -> int:
    effective_timeout = args.timeout if args.timeout is not None else settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    service = DirectorService(
        store=store,
        adapter=adapter,
        search_backend=make_search_backend(args, settings),
        progress=print_progress,
        default_craft_mode=getattr(args, "craft_mode", None) or settings.craft_mode,
        default_craft_options=craft_options_from_args(args, settings),
    )
    bot = FeishuBotService(store=store, director=service)
    print("启动 ai-novelist 飞书长连接机器人。", file=sys.stderr)
    run_feishu_long_connection(settings, bot.handle_text)
    return 0


def print_turn_choices(choices) -> None:
    if not choices:
        return
    print("请选择：")
    for index, choice in enumerate(choices, start=1):
        value = getattr(choice, "value", str(index))
        label = getattr(choice, "label", str(choice))
        print(f"  {value}. {label}")


def select_chat_graph(
    state: NovelState,
    user_input: str,
    research_graph,
    outline_graph,
    chat_graph,
    adapter: AgentAdapter | None = None,
    store: LocalStore | None = None,
):
    return chat_graph


def director_selects_research(state: NovelState, adapter: AgentAdapter, store: LocalStore) -> bool:
    if state.reference_brief.strip():
        return False
    try:
        output = adapter.complete(build_director_prompt(state), store.project_dir(state.project_id))
    except AgentAdapterError:
        return False
    return parse_director_decision(output)["action"] == "research"


def should_use_research_graph(state: NovelState, user_input: str) -> bool:
    return detect_research_need_text(user_input, has_reference_brief=bool(state.reference_brief.strip()))


def should_use_outline_graph(state: NovelState, user_input: str) -> bool:
    if state.active_workflow != "outline":
        return False
    return not is_project_status_request(user_input)


def is_project_status_request(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"status", "show status"} or any(marker in text for marker in ("查看状态", "项目状态", "显示状态"))


def is_project_context_request(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in {"reference", "references", "research", "show reference", "show references"}:
        return True
    markers = (
        "当前获取的信息",
        "获取的信息",
        "搜集到的信息",
        "搜索的信息",
        "检索信息",
        "调研信息",
        "参考简报",
        "参考信息",
        "来源列表",
        "当前信息",
    )
    return any(marker in text for marker in markers)


def print_project_startup_context(state: NovelState, store: LocalStore) -> None:
    lines = [
        f"Director> 当前项目状态：{state.project_id}",
        f"- 参考简报：{'已有' if state.reference_brief.strip() else '暂无'}",
        f"- 大纲：{'已锁定' if state.outline_stage == 'done' and state.outline.strip() else '阶段共创中' if state.active_workflow == 'outline' else '暂无'}",
        f"- 大纲阶段：{state.outline_stage} / {state.outline_stage_status}",
        f"- 世界观：{'已有' if state.worldbuilding.strip() else '暂无'}",
        f"- 章节细纲：{'已有' if state.chapter_plan.strip() else '暂无'}",
        f"- 章节正文：{'已有' if state.chapter_draft.strip() else '暂无'}",
        f"- 定稿章节：{'已有' if state.current_final_chapter.strip() else '暂无'}",
    ]
    if state.retrieval_query.strip():
        lines.append(f"- 最近检索：{state.retrieval_query.strip()}")
    if state.reference_brief.strip():
        lines.append(f"- 参考简报路径：{store.reference_brief_path(state.project_id)}")
        lines.append("你可以说：查看当前获取的信息，或基于这些资料生成大纲。")
    elif state.outline.strip():
        lines.append("你可以说：查看大纲、修改大纲、写第 1 章。")
    else:
        lines.append("你可以说：调研某本书、给我几个方向、或生成大纲。")
    print("\n".join(lines))


def print_progress(stage: str, message: str) -> None:
    print(f"[{stage}] {message}", flush=True)


def print_chat_turn_result(state: NovelState, store: LocalStore) -> None:
    if state.director_action in {"show_outline", "show_reference"}:
        print(f"Director> {state.director_message}")
        return

    if state.director_message:
        print(f"Director> {state.director_message}")

    if state.director_action == "research":
        print_research_result(state, store)
    elif state.director_action in {"run_outline_stage", "advance_outline_stage", "show_outline_stage", "generate_outline", "revise_outline", "review_outline", "compare_versions"}:
        print_outline_artifacts(state)
    elif state.director_action == "propose_directions":
        print_direction_proposal(state)



def print_research_result(state: NovelState, store: LocalStore) -> None:
    if state.reference_brief:
        print("\n参考简报：")
        print(state.reference_brief)
    if state.research_sources:
        print("\n来源：")
        for item in state.research_sources:
            title = item.get("title", "无标题")
            url = item.get("url", "")
            print(f"- {title}: {url}")
    if state.reference_brief:
        print(f"\n参考简报已保存：{store.reference_brief_path(state.project_id)}")
        print(f"来源列表已保存：{store.research_sources_path(state.project_id)}")


def print_outline_artifacts(state: NovelState) -> None:
    artifact = state.outline_stage_artifacts.get(state.outline_stage)
    if artifact:
        print(f"\n当前大纲阶段：{artifact.get('label', state.outline_stage)} / {state.outline_stage_status}")
        synthesis = str(artifact.get("synthesis", "")).strip()
        if synthesis:
            print(synthesis)
    if state.outline:
        print("\n当前大纲：")
        print(state.outline)
    if state.editor_notes:
        print("\n最近编辑意见：")
        print(state.editor_notes)


def print_locked_constraints(state: NovelState) -> None:
    if state.locked_constraints:
        print("\n锁定约束：")
        for item in state.locked_constraints:
            print(f"- {item}")


def print_direction_proposal(state: NovelState) -> None:
    directions = latest_outline_version_content(state, "directions")
    if directions:
        print("\n方向提案：")
        print(directions)


def latest_outline_version_content(state: NovelState, kind: str) -> str:
    for item in reversed(state.outline_versions):
        if item.get("kind") == kind:
            return str(item.get("content", ""))
    return ""


def looks_like_story_idea(text: str) -> bool:
    markers = ("想写", "小说", "故事", "主角", "世界", "城市", "科幻", "悬疑", "奇幻")
    return any(marker in text for marker in markers)


def run_writer_command(
    args: argparse.Namespace,
    store: LocalStore,
    settings: Settings,
    task: AgentTask,
) -> int:
    state = store.load_state(args.project)
    if hasattr(args, "chapter") and args.chapter:
        if args.chapter < 1:
            print("错误：章节编号必须大于 0", file=sys.stderr)
            return 2
        state.current_chapter = args.chapter
    state.review_status = "draft"
    state.error = ""
    apply_craft_args_to_state(state, args, settings)
    store.save_state(state)

    effective_timeout = args.timeout if args.timeout is not None else settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    if task == "plan_outline":
        state.user_request = "请启动或继续阶段化大纲共创"
        state.active_workflow = "outline"
        append_message(state, "user", state.user_request)
        store.save_state(state)
        graph = build_outline_collaboration_graph(adapter, store, progress=print_progress)
        result = NovelState.from_dict(graph.invoke(state.to_dict()))
        print_outline_turn_result(result, store)
        if args.auto_approve and result.outline_stage_status == "options_ready" and result.outline_stage != "done":
            result.user_request = "确认进入下一阶段"
            append_message(result, "user", result.user_request)
            store.save_state(result)
            result = NovelState.from_dict(graph.invoke(result.to_dict()))
            print_outline_turn_result(result, store)
        return 1 if result.error else 0

    graph = build_writer_graph(adapter, store, task, review_func=make_writer_review_func(args.auto_approve))
    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    if result.error:
        print(f"错误：{result.error}", file=sys.stderr)
    print(f"审核状态：{result.review_status}")
    if result.review_status == "approved":
        print_persisted_path(task, result, store)
    return 1 if result.review_status == "error" else 0




def run_finalize_command(
    args: argparse.Namespace,
    store: LocalStore,
    settings: Settings,
) -> int:
    if args.chapter < 1:
        print("错误：章节编号必须大于 0", file=sys.stderr)
        return 2
    state = store.load_state(args.project)
    state.current_chapter = args.chapter
    state.active_chapter = args.chapter
    state.director_action = "finalize_chapter"
    state.director_task_args = {"chapter": args.chapter, "explicit_finalize": True}
    state.user_request = f"定稿第 {args.chapter} 章"
    state.error = ""
    apply_craft_args_to_state(state, args, settings)
    store.save_state(state)

    effective_timeout = args.timeout if args.timeout is not None else settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    from ai_novelist.graph_finalize import build_finalize_graph

    result = NovelState.from_dict(build_finalize_graph(adapter, store).invoke(state.to_dict()))
    if result.error:
        print(f"错误：{result.error}", file=sys.stderr)
        return 1
    print(result.director_message)
    return 0


def run_export_command(args: argparse.Namespace, store: LocalStore) -> int:
    state = store.load_state(args.project)
    state.director_action = "export_project"
    state.error = ""
    store.save_state(state)
    from ai_novelist.graph_export import build_export_graph

    result = NovelState.from_dict(build_export_graph(store).invoke(state.to_dict()))
    if result.error:
        print(f"错误：{result.error}", file=sys.stderr)
        return 1
    print(result.director_message)
    return 0

def make_search_backend(args: argparse.Namespace, settings: Settings) -> SearchBackend:
    fallback_backend: SearchBackend
    if args.mock:
        fallback_backend = MockSearchBackend()
    else:
        provider = (args.search_provider or settings.search_provider).strip().lower()
        if provider in {"", "mock"}:
            fallback_backend = MockSearchBackend()
        else:
            fallback_backend = WebSearchBackend(
                provider=provider,
                api_key=search_api_key(provider) or settings.search_api_key,
                base_url=settings.search_base_url,
                timeout_seconds=settings.search_timeout_seconds,
            )

    local_corpus_dir = (getattr(args, "local_corpus_dir", None) or settings.local_corpus_dir).strip()
    if not local_corpus_dir:
        return fallback_backend
    return LocalFirstSearchBackend(LocalRAGSearchBackend(local_corpus_dir), fallback_backend)


def make_agent_adapter(args: argparse.Namespace, settings: Settings, timeout_seconds: int | None) -> AgentAdapter:
    if args.mock:
        return CodexCLIAdapter(timeout_seconds=timeout_seconds, mock=True)

    provider = (args.provider or settings.model_provider).strip().lower()
    if provider == "codex":
        return CodexCLIAdapter(codex_bin=settings.codex_bin, timeout_seconds=timeout_seconds)
    if provider == "deepseek":
        return DeepSeekAdapter(
            api_key=settings.deepseek_api_key,
            model=args.model or settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            timeout_seconds=timeout_seconds,
        )
    raise LocalStoreError(f"Unsupported model provider: {provider}")


def print_real_mode_notice(mock: bool, adapter: AgentAdapter, timeout_seconds: int | None) -> None:
    if mock:
        return
    if isinstance(adapter, DeepSeekAdapter):
        if timeout_seconds is None:
            detail = "不设置内部超时"
        else:
            detail = f"最长等待 {timeout_seconds} 秒"
        print(
            f"正在调用 DeepSeek API，模型 {adapter.model}，{detail}。",
            file=sys.stderr,
        )
        return
    if timeout_seconds is None:
        detail = "不设置内部超时"
    else:
        detail = f"最长等待 {timeout_seconds} 秒"
    print(f"正在调用 Codex CLI，{detail}。首次运行可能需要先完成 codex login。", file=sys.stderr)


def make_outline_review_func(auto_approve: bool):
    def review(state: NovelState) -> str:
        print("\n生成的大纲：")
        print(state.outline)
        if auto_approve:
            print("\n已自动确认。")
            return "approve"
        return input("\n请输入审核结果 approve/reject：")

    return review


def make_writer_review_func(auto_approve: bool):
    def review(state: NovelState, task: AgentTask) -> str:
        print(f"\n生成的{task_display_name(task)}：")
        print(task_output(state, task))
        if auto_approve:
            print("\n已自动确认。")
            return "approve"
        return input("\n请输入审核结果 approve/revise/stop：")

    return review


def make_compose_review_func(auto_approve: bool):
    def review(state: NovelState) -> str:
        print("\nCompose 工作流已完成自动编辑审稿：")
        print(f"编辑结论：{state.editor_decision}")
        print(f"质量分：{state.quality_score}")
        print(f"修订次数：{state.revision_count}")
        print("\n编辑意见：")
        print(state.editor_notes)
        if auto_approve:
            print("\n已自动确认并保存全部产物。")
            return "approve"
        return input("\n请输入最终人工审核结果 approve/revise/stop：")

    return review


def print_persisted_path(task: AgentTask, state: NovelState, store: LocalStore) -> None:
    if task == "plan_outline":
        print(f"总大纲已保存：{store.outline_path(state.project_id)}")
    elif task == "plan_chapters":
        print(f"章节细纲已保存：{store.chapter_plan_path(state.project_id)}")
    elif task == "write_chapter":
        print(f"章节正文已保存：{store.chapter_path(state.project_id, state.current_chapter)}")
    elif task == "review":
        print(f"编辑意见已保存：{store.editor_notes_path(state.project_id, state.current_chapter)}")


def print_compose_paths(state: NovelState, store: LocalStore) -> None:
    print("Compose 产物已保存：")
    print(f"世界观：{store.worldbuilding_path(state.project_id)}")
    print(f"总大纲：{store.outline_path(state.project_id)}")
    print(f"章节细纲：{store.chapter_plan_path(state.project_id)}")
    print(f"章节正文：{store.chapter_path(state.project_id, state.current_chapter)}")
    print(f"编辑意见：{store.editor_notes_path(state.project_id, state.current_chapter)}")


def show_project(args: argparse.Namespace, store: LocalStore) -> int:
    state = store.load_state(args.project)
    print(f"项目：{state.project_id}")
    print(f"标题：{state.title}")
    if state.idea:
        print(f"创意：{state.idea}")
    print(f"审核状态：{state.review_status}")
    print(f"当前章节：{state.current_chapter}")
    print(f"编辑结论：{state.editor_decision}")
    print(f"质量分：{state.quality_score}")
    print(f"修订次数：{state.revision_count}/{state.max_revisions}")
    print(f"大纲版本数：{len(state.outline_versions)}")
    if state.style_preferences:
        print("风格偏好：" + "，".join(state.style_preferences))
    if state.revision_instruction:
        print(f"最近修订要求：{state.revision_instruction}")
    print(artifact_status("参考简报", state.reference_brief, store.reference_brief_path(state.project_id)))
    print(artifact_status("世界观", state.worldbuilding, store.worldbuilding_path(state.project_id)))
    print(artifact_status("总大纲", state.outline, store.outline_path(state.project_id)))
    print(artifact_status("章节细纲", state.chapter_plan, store.chapter_plan_path(state.project_id)))
    print(artifact_status("章节正文", state.chapter_draft, store.chapter_path(state.project_id, state.current_chapter)))
    print(artifact_status("定稿章节", state.current_final_chapter, store.final_chapter_path(state.project_id, state.current_chapter)))
    print(artifact_status("编辑意见", state.editor_notes, store.editor_notes_path(state.project_id, state.current_chapter)))
    manuscript_path = store.manuscript_export_path(state.project_id)
    if manuscript_path.exists():
        print(f"导出手稿：已保存 -> {manuscript_path}")
    if state.director_action:
        print(f"Director 动作：{state.director_action}")
    if state.error:
        print(f"错误：{state.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
