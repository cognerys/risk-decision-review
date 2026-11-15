"""Shared desk-graph state. See docs/design.md."""

from __future__ import annotations

from typing import Any, TypedDict


class DeskState(TypedDict):
    card_id: str
    arm: str
    visible: dict[str, Any]
    evidence: list[Any]
    recommendation: dict[str, Any]
    trace: list[Any]
