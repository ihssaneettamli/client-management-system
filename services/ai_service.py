import json
import socket
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import requests

from models import get_clients_and_tasks_for_user


OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"  


class OllamaError(RuntimeError):
    pass


class OllamaNotRunningError(OllamaError):
    pass


class OllamaModelNotFoundError(OllamaError):
    pass


class OllamaTimeoutError(OllamaError):
    pass


def _is_port_open(host: str, port: int, timeout_s: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def ollama_generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    timeout_s: int = 60,
) -> str:
    """Call Ollama /api/generate and return the combined 'response' text."""

    if not _is_port_open("localhost", 11434, timeout_s=1.0):
        raise OllamaNotRunningError("Ollama is not running.")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }

    try:
        resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=timeout_s)
    except requests.exceptions.Timeout as e:
        raise OllamaTimeoutError("Ollama request timed out. Please try again.") from e
    except requests.exceptions.ConnectionError as e:
        raise OllamaNotRunningError("Ollama is not running.") from e

    try:
        data = resp.json()
    except Exception:
        data = None

    if resp.status_code != 200:
        msg = "Ollama error."
        if isinstance(data, dict):
            msg = data.get("error") or msg
        if "not found" in (msg or "").lower() or "model" in (msg or "").lower():
            raise OllamaModelNotFoundError(
                f"Model not found in Ollama: {model}. Install it with: ollama pull {model}"
            )
        raise OllamaError(msg)

    if not isinstance(data, dict):
        raise OllamaError("Unexpected Ollama response.")

    response_text = data.get("response")
    if not isinstance(response_text, str):
        raise OllamaError("Ollama response missing 'response' field.")

    return response_text


def _safe_truncate_text(s: str, limit: int = 12000) -> str:
    if s is None:
        return ""
    s = str(s)
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def build_context_payload(
    user_id: int,
    question: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Step-10 Context: Always send structured JSON to Ollama."""

    rows = get_clients_and_tasks_for_user(user_id=user_id)

    clients_map: Dict[str, Dict[str, Any]] = {}
    tasks: List[Dict[str, Any]] = []

    for r in rows:
        client_name = r.get("client_name")
        client_email = r.get("client_email")
        client_phone = r.get("client_phone")
        client_company = r.get("client_company")
        client_address = r.get("client_address")
        client_created_at = r.get("client_created_at")

        key = f"{client_name}|{client_email}".lower().strip()
        if key not in clients_map:
            clients_map[key] = {
                "name": client_name,
                "email": client_email,
                "phone": client_phone,
                "company": client_company,
                "address": client_address,
                "created_at": client_created_at,
            }

        if r.get("task_title"):
            tasks.append(
                {
                    "title": r.get("task_title"),
                    "description": r.get("task_description"),
                    "priority": r.get("task_priority"),
                    "status": r.get("task_status"),
                    "due_date": r.get("task_due_date"),
                    "client_name": client_name,
                }
            )

    clients = list(clients_map.values())

    pending_tasks = [t for t in tasks if t.get("status") == "Pending"]
    in_progress_tasks = [t for t in tasks if t.get("status") == "In Progress"]
    completed_tasks = [t for t in tasks if t.get("status") == "Completed"]

    total_clients = len(clients)
    total_tasks = len(tasks)

    stats = {
        "total_clients": total_clients,
        "total_tasks": total_tasks,
        "tasks": {
            "pending": len(pending_tasks),
            "in_progress": len(in_progress_tasks),
            "completed": len(completed_tasks),
        },
        "completion_rate": round(len(completed_tasks) / total_tasks * 100, 1)
        if total_tasks > 0
        else 0,
    }

    payload: Dict[str, Any] = {
        "clients": clients,
        "tasks": tasks,
        "statistics": stats,
        "question": question,
    }
    if extra:
        payload.update(extra)
    return payload


def smart_priority_sort(
    tasks: List[Dict[str, Any]],
    today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Step-9 Smart Priority sorting."""

    if today is None:
        today = date.today()

    def parse_due(d: Any) -> Optional[date]:
        if not d:
            return None
        try:
            return datetime.strptime(str(d), "%Y-%m-%d").date()
        except Exception:
            return None

    def bucket(t: Dict[str, Any]) -> int:
        pr = t.get("priority")
        st = t.get("status")
        due = parse_due(t.get("due_date"))

        if pr == "High" and st == "Pending":
            return 1
        if pr == "High" and due == today:
            return 2
        if pr == "Medium" and st == "Pending":
            return 3
        if pr == "Low":
            return 4
        return 5

    def due_rank(t: Dict[str, Any]) -> int:
        due = parse_due(t.get("due_date"))
        if due is None:
            return 999999
        return (due - today).days

    enumerated = list(enumerate(tasks))
    enumerated.sort(key=lambda it: (bucket(it[1]), due_rank(it[1]), it[0]))
    return [t for _, t in enumerated]


def ask_ai(question: str, user_id: int, mode: str = "chat", model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Ask Ollama with persistent per-user conversation memory (latest 20 messages).

    Every message saved contains:
      - role
      - content
      - timestamp
    """

    from services.chat_history_utils import (
        CHAT_HISTORY_LIMIT,
        add_chat_message,
        get_chat_history_for_user,
    )
    from services.chat_ai_service import build_prompt_with_conversation, trim_messages

    # Load previous conversation
    conversation = trim_messages(get_chat_history_for_user(user_id=user_id), CHAT_HISTORY_LIMIT)

    # Append new user message to the in-prompt conversation
    now_ts = datetime.now().isoformat(timespec="seconds")
    conversation = trim_messages(
        conversation + [{"role": "user", "content": question, "timestamp": now_ts}],
        CHAT_HISTORY_LIMIT,
    )

    # Build base DB context as before
    extra: Dict[str, Any] = {}
    if mode in {"recommendations", "smart_priority"}:
        base = build_context_payload(user_id=user_id, question=question)
        sorted_tasks = smart_priority_sort(base.get("tasks", []))
        extra["tasks_sorted_by_priority"] = sorted_tasks

        payload = base
        payload["tasks"] = sorted_tasks
        structured = payload
    else:
        structured = build_context_payload(user_id=user_id, question=question)

    structured_json = json.dumps(structured, ensure_ascii=False)

    system_instructions = (
        "You are a local AI assistant for a Smart Client Management System. "
        "You must answer in natural English. "
        "Use the provided JSON context to make accurate observations and recommendations. "
        "Do not claim you executed database writes. "
        "If asked to list or count, ensure numbers are consistent with the context."
    )

    if mode == "sql_helper":
        system_instructions += (
            " When asked about SQL: respond with ONLY a safe SELECT-only SQL query suggestion. "
            "Never include INSERT/UPDATE/DELETE/DROP/ALTER/COPY/ATTACH, never use multiple statements. "
            "Use placeholders like ? for user_id when needed."
        )

    prompt = build_prompt_with_conversation(
        system_instructions=system_instructions,
        context_json=_safe_truncate_text(structured_json),
        conversation_messages=conversation,
        latest_user_question=question,
    )


    answer = ollama_generate(prompt=prompt, model=model).strip()

    # Save both sides into DB
    add_chat_message(user_id=user_id, role="user", content=question, timestamp=now_ts)
    assistant_ts = datetime.now().isoformat(timespec="seconds")
    add_chat_message(
        user_id=user_id,
        role="assistant",
        content=answer,
        timestamp=assistant_ts,
    )

    return {"answer": answer, "mode": mode}


import sqlite3


def generate_insights(user_id: int, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect("instance/database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, created_at FROM clients ORDER BY created_at DESC LIMIT 5"
        )
        recent_clients = cursor.fetchall()
        conn.close()

        if recent_clients:
            clients_summary = "\n".join(
                [
                    f"- Client Name: {row[0]}, Added on: {row[1]}"
                    for row in recent_clients
                ]
            )
        else:
            clients_summary = "No recent clients found in the database."
    except Exception as e:
        clients_summary = f"Database connection issue: {str(e)}"

    question = f"""
    You are a professional business assistant. Generate strategic business insights based on my recent database activity.
    Return sharp, actionable bullet points in natural English.

    Recent Clients Activity:
    {clients_summary}
    """

    return ask_ai(question=question, user_id=user_id, mode="insights", model=model)


def generate_recommendations(user_id: int, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    question = (
        "Generate practical recommendations and a prioritized to-do list. "
        "Use smart priority rules (High+Pending, High+Due Today, Medium+Pending, Low). "
        "Explain why the top items come first."
    )
    return ask_ai(question=question, user_id=user_id, mode="recommendations", model=model)


def generate_daily_summary(user_id: int, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    question = (
        "Summarize today's work: new clients, completed tasks, pending tasks, high priority work, "
        "and a focus suggestion for tomorrow."
    )
    return ask_ai(question=question, user_id=user_id, mode="daily_summary", model=model)


def generate_weekly_report(user_id: int, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    question = (
        "Create a weekly report including: clients added, tasks completed, pending tasks, high priority "
        "tasks, performance, and a short AI conclusion."
    )
    return ask_ai(question=question, user_id=user_id, mode="weekly_report", model=model)


def explain_dashboard(question: str, user_id: int, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    return ask_ai(question=question, user_id=user_id, mode="explain_dashboard", model=model)


def sql_helper(question: str, user_id: int, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    return ask_ai(question=question, user_id=user_id, mode="sql_helper", model=model)

