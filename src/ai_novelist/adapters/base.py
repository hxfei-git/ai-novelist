"""Adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class AgentAdapterError(RuntimeError):
    """Raised when an agent adapter cannot produce a usable response."""


class AgentAdapter(ABC):
    @abstractmethod
    def complete(self, prompt: str, workspace: Path) -> str:
        """Return a text completion for the given prompt."""
