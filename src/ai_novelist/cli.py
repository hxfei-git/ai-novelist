"""Command line interface."""

from __future__ import annotations

import argparse
import sys

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.adapters.deepseek import DeepSeekAdapter
from ai_novelist.config import Settings, load_settings
from ai_novelist.graph_minimal import build_minimal_graph
from ai_novelist.graph_outline import build_outline_collaboration_graph
from ai_novelist.graph_research import build_research_graph, detect_research_need_text
from ai_novelist.research import MockSearchBackend, SearchBackend, SearchBackendError, WebSearchBackend
from ai_novelist.graph_writer import (
    AgentTask,
    append_message,
    artifact_status,
    build_chat_graph,
    build_composer_graph,
    build_writer_graph,
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
        if args.command == "worldbuild":
            return run_writer_command(args, store, settings, "worldbuild")
        if args.command == "plan-outline":
            return run_writer_command(args, store, settings, "plan_outline")
        if args.command == "plan-chapters":
            return run_writer_command(args, store, settings, "plan_chapters")
        if args.command == "write-chapter":
            return run_writer_command(args, store, settings, "write_chapter")
        if args.command == "review":
            return run_writer_command(args, store, settings, "review")
        if args.command == "show":
            return show_project(args, store)
    except (LocalStoreError, SearchBackendError) as exc:
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
    chat_parser.add_argument("--model", help="模型名；DeepSeek 默认 deepseek-chat")
    chat_parser.add_argument(
        "--search-provider",
        choices=("mock", "serpapi", "tavily", "exa"),
        help="搜索提供方，默认读 AI_NOVELIST_SEARCH_PROVIDER；--mock 会强制使用 mock",
    )

    worldbuild_parser = subparsers.add_parser("worldbuild", help="生成世界观设定")
    worldbuild_parser.add_argument("--project", required=True, help="项目 ID")
    add_generation_flags(worldbuild_parser)

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

    show_parser = subparsers.add_parser("show", help="显示项目状态")
    show_parser.add_argument("--project", required=True, help="项目 ID")

    return parser


def add_generation_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mock", action="store_true", help="使用本地 mock 输出，不调用真实模型")
    parser.add_argument("--auto-approve", action="store_true", help="跳过人工输入并自动确认")
    parser.add_argument("--timeout", type=int, help="真实模型调用超时时间，单位秒")
    parser.add_argument("--provider", choices=("codex", "deepseek"), help="模型提供方，默认读 AI_NOVELIST_MODEL_PROVIDER")
    parser.add_argument("--model", help="模型名；DeepSeek 默认 deepseek-chat")


def init_project(args: argparse.Namespace, store: LocalStore) -> int:
    state = store.create_project(args.title, args.project)
    print(f"项目已创建：{state.project_id}")
    print(f"目录：{store.project_dir(state.project_id)}")
    return 0


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
    append_message(state, "user", state.user_request)
    store.save_state(state)

    effective_timeout = args.timeout or settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    graph = build_outline_collaboration_graph(adapter, store)
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
    if state.locked_constraints:
        print("锁定约束：" + "，".join(state.locked_constraints))
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
    store.save_state(state)

    effective_timeout = args.timeout or settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
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

    effective_timeout = args.timeout or settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    chat_graph = build_chat_graph(adapter, store, progress=print_progress)
    outline_graph = build_outline_collaboration_graph(adapter, store)
    research_graph = build_research_graph(make_search_backend(args, settings), store, adapter=adapter, progress=print_progress)

    print(f"进入 ai-novelist chat：项目 {state.project_id}。输入 exit/quit/退出 结束。")
    while True:
        try:
            user_input = input("你> ").strip()
        except EOFError:
            print()
            break
        if not user_input:
            continue
        current_state = store.load_state(args.project)
        if user_input.lower() in {"exit", "quit"} or user_input in {"退出", "结束"}:
            print("Director> 已结束本次创作对话。")
            break

        state = current_state
        state.user_request = user_input
        append_message(state, "user", user_input)
        if not state.idea and looks_like_story_idea(user_input):
            state.idea = user_input
        store.save_state(state)

        graph = select_chat_graph(state, user_input, research_graph, outline_graph, chat_graph)
        result = NovelState.from_dict(graph.invoke(state.to_dict()))
        print_chat_turn_result(result, store)
        if result.error:
            print(f"错误：{result.error}", file=sys.stderr)
            return 1
        if result.director_action == "stop":
            break
    return 0


def select_chat_graph(state: NovelState, user_input: str, research_graph, outline_graph, chat_graph):
    if should_use_research_graph(state, user_input):
        return research_graph
    if should_use_outline_graph(state, user_input):
        return outline_graph
    return chat_graph


def should_use_research_graph(state: NovelState, user_input: str) -> bool:
    return detect_research_need_text(user_input, has_reference_brief=bool(state.reference_brief.strip()))


def should_use_outline_graph(state: NovelState, user_input: str) -> bool:
    if state.active_workflow != "outline":
        return False
    return not is_project_status_request(user_input)


def is_project_status_request(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"status", "show status"} or any(marker in text for marker in ("查看状态", "项目状态", "显示状态"))


def print_progress(stage: str, message: str) -> None:
    print(f"[{stage}] {message}", flush=True)


def print_chat_turn_result(state: NovelState, store: LocalStore) -> None:
    if state.director_action == "show_outline":
        print(f"Director> {state.director_message}")
        return

    if state.director_message:
        print(f"Director> {state.director_message}")

    if state.director_action == "research":
        print_research_result(state, store)
    elif state.director_action in {"generate_outline", "revise_outline", "review_outline", "compare_versions"}:
        print_outline_artifacts(state)
    elif state.director_action == "propose_directions":
        print_direction_proposal(state)

    print_locked_constraints(state)


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
    store.save_state(state)

    effective_timeout = args.timeout or settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    graph = build_writer_graph(adapter, store, task, review_func=make_writer_review_func(args.auto_approve))
    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    if result.error:
        print(f"错误：{result.error}", file=sys.stderr)
    print(f"审核状态：{result.review_status}")
    if result.review_status == "approved":
        print_persisted_path(task, result, store)
    return 1 if result.review_status == "error" else 0


def make_search_backend(args: argparse.Namespace, settings: Settings) -> SearchBackend:
    if args.mock:
        return MockSearchBackend()

    provider = (args.search_provider or settings.search_provider).strip().lower()
    if provider in {"", "mock"}:
        return MockSearchBackend()
    return WebSearchBackend(
        provider=provider,
        api_key=settings.search_api_key,
        base_url=settings.search_base_url,
        timeout_seconds=settings.search_timeout_seconds,
    )


def make_agent_adapter(args: argparse.Namespace, settings: Settings, timeout_seconds: int) -> AgentAdapter:
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


def print_real_mode_notice(mock: bool, adapter: AgentAdapter, timeout_seconds: int) -> None:
    if mock:
        return
    if isinstance(adapter, DeepSeekAdapter):
        print(
            f"正在调用 DeepSeek API，模型 {adapter.model}，最长等待 {timeout_seconds} 秒。",
            file=sys.stderr,
        )
        return
    print(f"正在调用 Codex CLI，最长等待 {timeout_seconds} 秒。首次运行可能需要先完成 codex login。", file=sys.stderr)


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
    if task == "worldbuild":
        print(f"世界观已保存：{store.worldbuilding_path(state.project_id)}")
    elif task == "plan_outline":
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
    if state.locked_constraints:
        print("锁定约束：" + "，".join(state.locked_constraints))
    if state.style_preferences:
        print("风格偏好：" + "，".join(state.style_preferences))
    if state.revision_instruction:
        print(f"最近修订要求：{state.revision_instruction}")
    print(artifact_status("参考简报", state.reference_brief, store.reference_brief_path(state.project_id)))
    print(artifact_status("世界观", state.worldbuilding, store.worldbuilding_path(state.project_id)))
    print(artifact_status("总大纲", state.outline, store.outline_path(state.project_id)))
    print(artifact_status("章节细纲", state.chapter_plan, store.chapter_plan_path(state.project_id)))
    print(artifact_status("章节正文", state.chapter_draft, store.chapter_path(state.project_id, state.current_chapter)))
    print(artifact_status("编辑意见", state.editor_notes, store.editor_notes_path(state.project_id, state.current_chapter)))
    if state.director_action:
        print(f"Director 动作：{state.director_action}")
    if state.error:
        print(f"错误：{state.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
