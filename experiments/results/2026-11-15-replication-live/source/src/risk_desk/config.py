"""Environment settings. The API key is never stored on Settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_LANGSMITH_PROJECT = "risk-desk-function"


def live_enabled() -> bool:
    """True only when RISK_DESK_LIVE is ``1`` or ``true``."""
    raw = os.environ.get("RISK_DESK_LIVE", "")
    return raw.strip().lower() in {"1", "true"}


def _or_default(name: str, default: str) -> str:
    raw = os.environ.get(name, "")
    text = raw.strip()
    return text or default


@dataclass(frozen=True)
class Settings:
    model: str = DEFAULT_MODEL
    live: bool = False
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    langsmith_project: str = DEFAULT_LANGSMITH_PROJECT

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            model=_or_default("RISK_DESK_MODEL", DEFAULT_MODEL),
            live=live_enabled(),
            reasoning_effort=_or_default(
                "RISK_DESK_REASONING_EFFORT", DEFAULT_REASONING_EFFORT
            ),
            langsmith_project=_or_default(
                "LANGSMITH_PROJECT", DEFAULT_LANGSMITH_PROJECT
            ),
        )
