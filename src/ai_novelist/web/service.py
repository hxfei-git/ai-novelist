"""Compatibility module for legacy Web service imports.

FastAPI routes and tests import focused Web modules directly. New code should
import project_service, outline_actions, chapter_outline_actions,
chapter_actions, review_actions, or outline_service as appropriate.
"""

from __future__ import annotations
