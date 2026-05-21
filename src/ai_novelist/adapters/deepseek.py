"""DeepSeek API adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError


class DeepSeekAPIError(AgentAdapterError):
    """Raised when DeepSeek API cannot produce a usable response."""


@dataclass
class DeepSeekAdapter(AgentAdapter):
    api_key: str = ""
    model: str = "deepseek-v4-pro"
    base_url: str = "https://api.deepseek.com"
    timeout_seconds: int = 180
    temperature: float = 0.7

    def complete(self, prompt: str, workspace: Path) -> str:
        del workspace
        if not self.api_key.strip():
            raise DeepSeekAPIError("DeepSeek API key is not configured; set DEEPSEEK_API_KEY")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": self.temperature,
        }
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

        text = self._extract_text(body)
        if not text.strip():
            raise DeepSeekAPIError("DeepSeek API returned empty output")
        return text

    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

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
