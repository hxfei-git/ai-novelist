"""Command line interface."""

from __future__ import annotations

import argparse
import sys

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.adapters.deepseek import DeepSeekAdapter
from ai_novelist.config import Settings, load_settings
from ai_novelist.graph_minimal import build_minimal_graph
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
    except LocalStoreError as exc:
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
    state = store.load_state(args.project)
    state.idea = args.idea
    state.review_status = "draft"
    state.error = ""
    store.save_state(state)

    effective_timeout = args.timeout or settings.codex_timeout_seconds
    adapter = make_agent_adapter(args, settings, effective_timeout)
    print_real_mode_notice(args.mock, adapter, effective_timeout)
    graph = build_minimal_graph(adapter, store, review_func=make_outline_review_func(args.auto_approve))
    result = NovelState.from_dict(graph.invoke(state.to_dict()))

    if result.error:
        print(f"错误：{result.error}", file=sys.stderr)
    print(f"审核状态：{result.review_status}")
    if result.review_status == "approved":
        print(f"大纲已保存：{store.outline_path(result.project_id)}")
        return 0
    return 1 if result.review_status == "error" else 0


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
    graph = build_chat_graph(adapter, store)

    print(f"进入 ai-novelist chat：项目 {state.project_id}。输入 exit/quit/退出 结束。")
    while True:
        try:
            user_input = input("你> ").strip()
        except EOFError:
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"} or user_input in {"退出", "结束"}:
            print("Director> 已结束本次创作对话。")
            break

        state = store.load_state(args.project)
        state.user_request = user_input
        append_message(state, "user", user_input)
        if not state.idea and looks_like_story_idea(user_input):
            state.idea = user_input
        store.save_state(state)

        result = NovelState.from_dict(graph.invoke(state.to_dict()))
        print(f"Director> {result.director_message}")
        if result.error:
            print(f"错误：{result.error}", file=sys.stderr)
            return 1
        if result.director_action == "stop":
            break
    return 0


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
