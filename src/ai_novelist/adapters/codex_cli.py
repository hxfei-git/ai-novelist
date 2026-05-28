"""Codex CLI adapter."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError, AgentCallOptions


class CodexCLIError(AgentAdapterError):
    """Raised when Codex CLI cannot produce a usable response."""


@dataclass
class CodexCLIAdapter(AgentAdapter):
    codex_bin: str = "codex"
    timeout_seconds: int | None = None
    mock: bool = False

    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if self.mock:
            from ai_novelist.adapters.mock_codex import MockCodexAdapter

            return MockCodexAdapter().complete(prompt, workspace, options)

        del options

        command = [
            self.codex_bin,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "-C",
            str(workspace),
            "-",
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                input=prompt,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise CodexCLIError(f"Codex CLI not found: {self.codex_bin}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CodexCLIError(f"Codex CLI timed out after {self.timeout_seconds}s") from exc

        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise CodexCLIError(f"Codex CLI failed with exit code {result.returncode}: {message}")

        text = self._extract_text(result.stdout)
        if not text.strip():
            raise CodexCLIError("Codex CLI returned empty output")
        return text

    def _extract_text(self, stdout: str) -> str:
        final_messages: list[str] = []
        raw_lines: list[str] = []

        for line in stdout.splitlines():
            if not line.strip():
                continue
            raw_lines.append(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = self._text_from_event(event)
            if message:
                final_messages.append(message)

        if final_messages:
            return final_messages[-1].strip()
        return "\n".join(raw_lines).strip()

    def _text_from_event(self, event: dict) -> str:
        for key in ("message", "content", "text", "last_message"):
            value = event.get(key)
            if isinstance(value, str):
                return value

        item = event.get("item")
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                return text
            content = item.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
                if parts:
                    return "\n".join(parts)

        return ""
