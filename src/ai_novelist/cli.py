"""Command line interface."""

from __future__ import annotations

import argparse
import sys

from ai_novelist.config import Settings, load_settings


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "web":
        parser.print_help()
        return 1

    from ai_novelist.web.app import run_web_command

    settings = load_settings()
    try:
        return run_web_command(args, settings)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-novelist")
    subparsers = parser.add_subparsers(dest="command")

    web_parser = subparsers.add_parser("web", help="启动本地 Web UI/API 服务")
    web_parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    web_parser.add_argument("--port", type=int, default=8000, help="监听端口")
    web_parser.add_argument("--mock", action="store_true", help="Web 生成接口默认使用本地 mock 输出")
    web_parser.add_argument("--timeout", type=int, help="真实模型调用超时时间，单位秒")
    web_parser.add_argument("--provider", choices=("codex", "deepseek"), help="模型提供方，默认读 AI_NOVELIST_MODEL_PROVIDER")
    web_parser.add_argument("--model", help="模型名；DeepSeek 默认 deepseek-v4-flash")

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
