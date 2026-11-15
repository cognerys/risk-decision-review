"""Local JSONL mirror. API keys, secrets, and tokens are not written."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from risk_desk.config import DEFAULT_LANGSMITH_PROJECT

MIRROR_PATH = Path("runs") / "mirror.jsonl"
_LOCK = threading.Lock()
_SENSITIVE_KEY_PARTS = ("key", "secret", "token")


def _sensitive_key(name: str) -> bool:
    lowered = name.casefold()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def redact(value: Any) -> Any:
    if isinstance(value, str):
        for name in ("OPENAI_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
            secret = os.environ.get(name, "")
            if secret:
                value = value.replace(secret, "[redacted]")
        return re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", value)
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if _sensitive_key(str(key)):
                continue
            if isinstance(item, str) and item.startswith("sk-"):
                continue
            cleaned[str(key)] = redact(item)
        return cleaned
    if isinstance(value, list):
        cleaned_list: list[Any] = []
        for item in value:
            if isinstance(item, str) and item.startswith("sk-"):
                continue
            cleaned_list.append(redact(item))
        return cleaned_list
    return value


def mirror_event(event: dict[str, Any]) -> None:
    """Append one redacted JSON line to ``runs/mirror.jsonl``."""
    cleaned = redact(event)
    line = json.dumps(cleaned, ensure_ascii=False, default=str)
    with _LOCK:
        MIRROR_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MIRROR_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _present(name: str) -> bool:
    return name in os.environ and bool(os.environ[name].strip())


def langsmith_env() -> dict[str, object]:
    """Project name and whether LangSmith env vars are set, without values."""
    project = os.environ.get("LANGSMITH_PROJECT", "").strip() or DEFAULT_LANGSMITH_PROJECT
    return {
        "project": project,
        "langsmith_tracing_present": _present("LANGSMITH_TRACING"),
        "langsmith_api_key_present": _present("LANGSMITH_API_KEY"),
    }
