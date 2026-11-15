"""Chat-model factory. Live calls stay behind RISK_DESK_LIVE, except probe."""

from __future__ import annotations

import os
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from risk_desk.config import Settings

STUB_CONTENT = (
    '{"action_or_abstain":"abstain","reason":"foundation_stub","evidence_ids":[]}'
)

# Explains the effort actually used after a live client is constructed.
# Empty until then so show-config can report the configured effort.
REASONING_NOTE = ""

_SK_VALUE = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]+")


def _stub_message() -> AIMessage:
    return AIMessage(content=STUB_CONTENT, tool_calls=[])


class ScriptedChatModel(BaseChatModel):
    """Offline model. ``invoke`` does not call a network."""

    @property
    def _llm_type(self) -> str:
        return "risk_desk_scripted"

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        return ChatResult(generations=[ChatGeneration(message=_stub_message())])

    def bind_tools(self, tools: Any, *args: Any, **kwargs: Any) -> ScriptedChatModel:
        del tools, args, kwargs
        return self


def reasoning_note_for(settings: Settings) -> str:
    """Note for show-config. Never includes an API key."""
    if REASONING_NOTE:
        return REASONING_NOTE
    return f"reasoning_effort={settings.reasoning_effort}"


def _redact_text(text: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        text = text.replace(api_key, "[redacted]")
    return _SK_VALUE.sub("[redacted]", text)


def _accepts_reasoning_effort(chat_cls: type) -> bool:
    fields = getattr(chat_cls, "model_fields", None)
    if isinstance(fields, dict) and "reasoning_effort" in fields:
        return True
    try:
        import inspect

        return "reasoning_effort" in inspect.signature(chat_cls).parameters
    except (TypeError, ValueError):
        return False


def _tool_calling_requires_none(exc: BaseException) -> bool:
    text = str(exc).lower()
    if "none" not in text:
        return False
    mentions_tools = "tool" in text or "function call" in text
    mentions_effort = "reasoning" in text or "effort" in text
    return mentions_tools and mentions_effort


def _build_live(settings: Settings, *, max_retries: int | None = None) -> Any:
    """Construct ``ChatOpenAI`` for ``settings.model``. Does not change the model id."""
    global REASONING_NOTE

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. risk_desk does not store or print the key."
        )

    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {"model": settings.model, "api_key": api_key}
    if max_retries is not None:
        kwargs["max_retries"] = max_retries

    effort = settings.reasoning_effort
    if not _accepts_reasoning_effort(ChatOpenAI):
        REASONING_NOTE = (
            "Installed ChatOpenAI does not accept reasoning_effort; "
            "the parameter was not passed. The model id was not changed."
        )
        return ChatOpenAI(**kwargs)

    kwargs["reasoning_effort"] = effort
    try:
        client = ChatOpenAI(**kwargs)
    except Exception as exc:
        if effort == "low" and _tool_calling_requires_none(exc):
            kwargs["reasoning_effort"] = "none"
            try:
                client = ChatOpenAI(**kwargs)
            except Exception as retry_exc:
                raise RuntimeError(_construction_error(retry_exc)) from None
            REASONING_NOTE = (
                "Constructing ChatOpenAI with reasoning_effort=low failed because "
                "tool calling requires reasoning_effort=none. Retried once with none. "
                "The model id was not changed."
            )
            return client
        raise RuntimeError(_construction_error(exc)) from None
    REASONING_NOTE = f"reasoning_effort={effort}"
    return client


def _construction_error(exc: BaseException) -> str:
    return "Live client construction failed. " + _redact_text(str(exc))


def build_chat_model(settings: Settings) -> BaseChatModel:
    """Scripted model when live mode is off. Live client only when it is on."""
    if not settings.live:
        return ScriptedChatModel()
    return _build_live(settings)


def _model_id_rejected(exc: BaseException) -> bool:
    try:
        from langchain_core.exceptions import ModelNotFoundError
    except ImportError:  # pragma: no cover
        model_not_found: tuple[type, ...] = ()
    else:
        model_not_found = (ModelNotFoundError,)
    if model_not_found and isinstance(exc, model_not_found):
        return True
    status = getattr(exc, "status_code", None)
    if status == 404:
        return True
    text = str(exc).lower()
    if "model" not in text:
        return False
    markers = (
        "model_not_found",
        "does not exist",
        "do not exist",
        "invalid model",
        "unknown model",
        "model not found",
        "not a valid model",
    )
    return any(marker in text for marker in markers)


def probe_model(settings: Settings) -> str:
    """One tiny live call. Raise if the endpoint rejects the model id."""
    client = _build_live(settings, max_retries=0)
    try:
        message = client.invoke([HumanMessage(content="ok")])
    except Exception as exc:
        detail = _redact_text(str(exc))
        if _model_id_rejected(exc):
            raise RuntimeError(
                f"Model id {settings.model!r} was rejected by the endpoint. "
                f"The model name was not changed. {detail}"
            ) from None
        raise RuntimeError(f"Live probe failed. {detail}") from None
    content = message.content
    if not isinstance(content, str):
        content = str(content)
    return content
