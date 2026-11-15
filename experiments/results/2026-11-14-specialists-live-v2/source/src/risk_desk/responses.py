"""Decode assistant text without confusing provider content blocks with proposals."""

from __future__ import annotations

import json
import re
from typing import Any

from risk_desk.tracing import redact


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(filter(None, (extract_text(block) for block in content)))
    if isinstance(content, dict) and content.get("type") in {"text", "output_text"}:
        text = content.get("text")
        return text if isinstance(text, str) else ""
    return ""


def decode_response(content: Any) -> dict[str, Any]:
    """Retain a redacted response, parse status and shape-checked proposal.

    Legal actions and evidence membership are evaluated separately by the verifier.
    Provider metadata, refusal and reasoning blocks are not decision JSON.
    """
    text = extract_text(content).strip()
    raw = redact(content)
    record: dict[str, Any] = {
        "raw_content": raw,
        "text": redact(text),
        "parse_status": "no_text",
        "proposal": {},
    }
    if not text:
        return record
    fenced = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", text, flags=re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else text
    try:
        proposal = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        record["parse_status"] = "invalid_json"
        return record
    valid = (
        isinstance(proposal, dict)
        and isinstance(proposal.get("action_or_abstain"), str)
        and isinstance(proposal.get("evidence_ids"), list)
        and all(isinstance(item, str) for item in proposal["evidence_ids"])
        and all(isinstance(proposal.get(key, ""), str)
                for key in ("reason", "procedural", "economic", "evidential"))
    )
    if not valid:
        record["parse_status"] = "invalid_shape"
        return record
    record["parse_status"] = "ok"
    record["proposal"] = redact(proposal)
    return record
