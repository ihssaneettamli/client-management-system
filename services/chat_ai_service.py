from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from services.chat_history_utils import CHAT_HISTORY_LIMIT


def format_conversation_for_prompt(messages: List[Dict[str, Any]]) -> str:
    """Format conversation with required fields: role/content/timestamp."""

    def safe_str(x: Any) -> str:
        return "" if x is None else str(x)

    parts: List[str] = []
    for m in messages:
        role = safe_str(m.get("role"))
        content = safe_str(m.get("content"))
        ts = safe_str(m.get("timestamp"))
        parts.append(
            f"{{\"role\": \"{role}\", \"content\": {json.dumps(content)}, \"timestamp\": \"{ts}\"}}"
        )

    return "[\n" + ",\n".join(parts) + "\n]"


def trim_messages(messages: List[Dict[str, Any]], limit: int = CHAT_HISTORY_LIMIT) -> List[Dict[str, Any]]:
    """Keep only latest N messages."""
    if len(messages) <= limit:
        return messages
    return messages[-limit:]


def build_prompt_with_conversation(
    *,
    system_instructions: str,
    context_json: str,
    conversation_messages: List[Dict[str, Any]],
    latest_user_question: str,
) -> str:
    convo = format_conversation_for_prompt(conversation_messages)

    return (
        system_instructions
        + "\n\n"
        + "CONTEXT_JSON:\n"
        + context_json
        + "\n\n"
        + "CONVERSATION_JSON (role/content/timestamp):\n"
        + convo
        + "\n\n"
        + "USER_QUESTION:\n"
        + latest_user_question
    )

