"""DeepSeek API adapter."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError, AgentCallOptions


class DeepSeekAPIError(AgentAdapterError):
    """Raised when DeepSeek API cannot produce a usable response."""


THINKING_DISABLED_MEDIUM_AGENTS = frozenset(
    {
        "outline_stage_role",
        "version_comparator",
        "dialogue_enhancer",
        "atmosphere_enhancer",
        "hook_enhancer",
        "restraint_polisher",
        "emotional_resonance_polisher",
        "style_normalizer",
        "outline_editor",
        "chapter_pacing_agent",
        "chapter_goal_agent",
        "restraint_agent",
        "ending_resonance_agent",
        "chapter_conflict_agent",
        "chapter_hook_agent",
        "scene_breakdown_agent",
        "scene_conflict_check_agent",
        "bible_update_extractor",
    }
)

THINKING_ENABLED_MEDIUM_AGENTS = frozenset(
    {
        "retrieval_context_synthesizer",
        "outline_stage_synthesizer",
        "outline_planner",
        "outline_reviser",
        "chapter_card_synthesizer",
        "scene_synthesizer",
        "chapter_writer",
        "bible_conflict_checker",
        "bible_update_synthesizer",
    }
)

THINKING_ENABLED_HIGH_AGENTS = frozenset()

FAST_AGENT_NAMES = THINKING_DISABLED_MEDIUM_AGENTS
SLOW_AGENT_NAMES = THINKING_ENABLED_MEDIUM_AGENTS | THINKING_ENABLED_HIGH_AGENTS

_AGENT_HEADER_RE = re.compile(r"^AGENT:\s*([A-Za-z0-9_\-]+)\s*$")


@dataclass
class DeepSeekAdapter(AgentAdapter):
    api_key: str = ""
    model: str = "deepseek-v4-pro"
    base_url: str = "https://api.deepseek.com"
    timeout_seconds: int | None = None
    temperature: float = 0.7

    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        del workspace
        if not self.api_key.strip():
            raise DeepSeekAPIError("DeepSeek API key is not configured; set DEEPSEEK_API_KEY")

        payload = self._build_payload(prompt, options)
        request = urllib.request.Request(
            self.chat_completions_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DeepSeekAPIError(f"DeepSeek API failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise DeepSeekAPIError(f"DeepSeek API request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise DeepSeekAPIError(f"DeepSeek API timed out after {self.timeout_seconds}s") from exc
        except OSError as exc:
            raise DeepSeekAPIError(f"DeepSeek API connection failed: {exc}") from exc

        text = self._extract_text(body)
        if not text.strip():
            raise DeepSeekAPIError("DeepSeek API returned empty output")
        return text

    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _build_payload(self, prompt: str, options: AgentCallOptions | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        strategy = self._thinking_strategy(self._agent_name(prompt, options))
        if strategy == "disabled-medium":
            payload["thinking"] = {"type": "disabled"}
            payload["temperature"] = self.temperature
        elif strategy == "enabled-high":
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = "high"
        else:
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = "medium"
        return payload

    def _agent_name(self, prompt: str, options: AgentCallOptions | None = None) -> str:
        if options and options.agent.strip():
            return options.agent.strip()
        first_line = prompt.splitlines()[0] if prompt.splitlines() else ""
        match = _AGENT_HEADER_RE.match(first_line.strip())
        return match.group(1) if match else ""

    def _thinking_strategy(self, agent: str) -> str:
        if agent in THINKING_DISABLED_MEDIUM_AGENTS:
            return "disabled-medium"
        if agent in THINKING_ENABLED_MEDIUM_AGENTS:
            return "enabled-medium"
        if agent in THINKING_ENABLED_HIGH_AGENTS:
            return "enabled-high"
        return "enabled-medium"

    def _extract_text(self, body: str) -> str:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise DeepSeekAPIError("DeepSeek API returned invalid JSON") from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise DeepSeekAPIError("DeepSeek API response missing choices")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"].strip()

        text = choices[0].get("text") if isinstance(choices[0], dict) else None
        if isinstance(text, str):
            return text.strip()

        raise DeepSeekAPIError("DeepSeek API response missing message content")
