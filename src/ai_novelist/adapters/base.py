"""Adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class AgentAdapterError(RuntimeError):
    """Raised when an agent adapter cannot produce a usable response."""


@dataclass(frozen=True)
class AgentCallOptions:
    """Optional metadata for a single agent call."""

    agent: str = ""
    task: str = ""
    stage: str = ""


class AgentAdapter(ABC):
    @abstractmethod
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        """Return a text completion for the given prompt."""
