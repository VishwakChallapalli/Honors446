"""Conversational layer for the Student Productivity Agent.

The :class:`ConversationAgent` is responsible for:

* turning a free-form student message ("I have a calc midterm next Tuesday and
  it's worth 25%") into a structured task,
* answering planning questions such as "what should I work on first?", and
* generating short, encouraging study recommendations.

When an ``OPENAI_API_KEY`` is available the agent delegates the heavy lifting
to an OpenAI chat model with a strict JSON schema.  Otherwise, the agent falls
back to a deterministic rule based parser so the project stays runnable without
any third-party credentials - which is essential for grading.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .planner import build_study_plan, summarize_workload
from .prioritizer import prioritize_tasks


SYSTEM_PROMPT = """You are StudyPilot, an AI academic productivity coach for
college students. You help them capture assignments, prioritize their workload,
and build realistic study plans.

When the user mentions a new assignment, exam, project, or deadline you MUST
respond ONLY with a compact JSON object that matches this schema:

{
  "intent": "create_task" | "ask_plan" | "ask_priority" | "smalltalk",
  "reply": "<short friendly reply to show the user>",
  "task": {                       // include only when intent == create_task
    "title": "...",
    "course": "...",
    "due_date": "YYYY-MM-DD",
    "estimated_hours": <number>,
    "weight": <number 0-100>,
    "difficulty": <integer 1-5>,
    "notes": "..."
  }
}

If the user is just chatting, set intent to "smalltalk" and omit the task
field.  Always answer in valid JSON - no Markdown, no commentary outside the
JSON object."""


@dataclass
class AgentReply:
    """Structured response returned to the Flask layer / front-end."""

    intent: str
    reply: str
    task: Optional[dict] = None
    plan: Optional[List[dict]] = None
    summary: Optional[Dict[str, Any]] = None
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "reply": self.reply,
            "task": self.task,
            "plan": self.plan,
            "summary": self.summary,
            "suggestions": self.suggestions,
        }


# ---------------------------------------------------------------------------
# Rule-based fallback parser
# ---------------------------------------------------------------------------

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_COURSE_PATTERN = re.compile(
    r"\b([A-Z]{2,4})\s?-?\s?(\d{3})\b"  # e.g. CSE 446, MAT-265
)

_PERCENT_PATTERN = re.compile(r"(\d{1,3})\s?%")
_HOURS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s?(?:h|hr|hrs|hours?)")
_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_MONTH_DAY = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_TASK_KEYWORDS = (
    "assignment", "homework", "hw", "project", "exam", "midterm", "final",
    "quiz", "lab", "essay", "paper", "presentation", "report", "deadline",
    "due", "submit",
)

# Plan vs. priority: check priority first so "what should I work on first?" does not
# match a loose "plan" heuristic.  Avoid bare "next" so "quiz next Tuesday" becomes
# a task, not a plan request.
_PLAN_KEYWORDS = (
    "study plan",
    "plan my",
    "my week",
    "weekly plan",
    "schedule for the",
    "build a plan",
)
_PRIORITY_KEYWORDS = (
    "priority",
    "most important",
    "urgent",
    "what should i work",
    "work on first",
    "which task first",
    "where should i start",
)


def _extract_date(text: str, today: date) -> Optional[str]:
    iso = _DATE_PATTERN.search(text)
    if iso:
        return iso.group(1)

    md = _MONTH_DAY.search(text)
    if md:
        raw_m = md.group(1).lower()
        mkey = "sept" if raw_m.startswith("sept") else raw_m[:3]
        month = _MONTHS.get(mkey)
        if month is not None:
            day = int(md.group(2))
            year = today.year
            try:
                candidate = date(year, month, day)
            except ValueError:
                return None
            if candidate < today:
                candidate = date(year + 1, month, day)
            return candidate.isoformat()

    slash = _SLASH_DATE.search(text)
    if slash:
        month = int(slash.group(1))
        day = int(slash.group(2))
        year_part = slash.group(3)
        if year_part:
            year = int(year_part)
            if year < 100:
                year += 2000
        else:
            year = today.year
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if not year_part and candidate < today:
            candidate = date(year + 1, month, day)
        return candidate.isoformat()

    lower = text.lower()
    if "today" in lower:
        return today.isoformat()
    if "tomorrow" in lower:
        return (today + timedelta(days=1)).isoformat()

    for name, weekday in _WEEKDAYS.items():
        if name in lower:
            delta = (weekday - today.weekday()) % 7
            if delta == 0 or "next" in lower:
                delta = delta or 7
            return (today + timedelta(days=delta)).isoformat()

    if "next week" in lower:
        return (today + timedelta(days=7)).isoformat()
    return None


def _extract_course(text: str) -> Optional[str]:
    match = _COURSE_PATTERN.search(text)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None


def _extract_weight(text: str) -> Optional[float]:
    match = _PERCENT_PATTERN.search(text)
    if not match:
        return None
    value = float(match.group(1))
    return min(value, 100.0)


def _extract_hours(text: str) -> Optional[float]:
    match = _HOURS_PATTERN.search(text)
    if not match:
        return None
    return float(match.group(1))


def _looks_like_task(text: str) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in _TASK_KEYWORDS) or bool(_DATE_PATTERN.search(text))


def _guess_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = cleaned.rstrip(".!?")
    if len(cleaned) > 80:
        cleaned = cleaned[:77] + "..."
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Untitled task"


def rule_based_parse(message: str, today: Optional[date] = None) -> AgentReply:
    today = today or date.today()
    lowered = message.lower().strip()

    if not lowered:
        return AgentReply(
            intent="smalltalk",
            reply="I'm here whenever you're ready. Tell me about an assignment or ask for a study plan!",
        )

    if any(k in lowered for k in _PRIORITY_KEYWORDS):
        return AgentReply(
            intent="ask_priority",
            reply="Tackle the highest-scored items first - they're either due soon or worth the most points.",
        )

    if any(k in lowered for k in _PLAN_KEYWORDS):
        return AgentReply(
            intent="ask_plan",
            reply="Here's the suggested plan for the next several days based on what's on your plate.",
        )

    if _looks_like_task(message):
        task = {
            "title": _guess_title(message),
            "course": _extract_course(message) or "General",
            "due_date": _extract_date(message, today),
            "estimated_hours": _extract_hours(message) or 2.0,
            "weight": _extract_weight(message) or 10.0,
            "difficulty": 3,
            "notes": message,
        }
        reply = "Got it - I added that to your task list and prioritized it."
        return AgentReply(intent="create_task", reply=reply, task=task)

    return AgentReply(
        intent="smalltalk",
        reply=(
            "I can help you capture assignments, prioritize them, and build a "
            "study plan. Try saying something like \"CSE 446 project due "
            "Friday, ~6 hours, worth 20%\"."
        ),
    )


# ---------------------------------------------------------------------------
# OpenAI-backed parser (used when an API key is available)
# ---------------------------------------------------------------------------


def _llm_parse(message: str, history: List[dict]) -> Optional[AgentReply]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    try:
        client = OpenAI(api_key=api_key)
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        chat = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in history[-6:]:
            chat.append({"role": turn["role"], "content": turn["content"]})
        chat.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model=model,
            messages=chat,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=400,
        )
        raw = response.choices[0].message.content or "{}"
        payload = json.loads(raw)
        return AgentReply(
            intent=payload.get("intent", "smalltalk"),
            reply=payload.get("reply", ""),
            task=payload.get("task"),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public agent
# ---------------------------------------------------------------------------


class ConversationAgent:
    """High level orchestration object used by the Flask app."""

    def __init__(self) -> None:
        self.history: List[dict] = []

    def reset(self) -> None:
        self.history.clear()

    def handle(self, message: str, tasks: List[dict]) -> AgentReply:
        message = (message or "").strip()
        reply = _llm_parse(message, self.history) or rule_based_parse(message)

        if reply.intent == "ask_plan":
            reply.plan = build_study_plan(tasks)
            reply.summary = summarize_workload(tasks)
        elif reply.intent == "ask_priority":
            top = prioritize_tasks(tasks)[:3]
            reply.suggestions = [
                f"{idx + 1}. {t['title']} ({t['priority']}, score {t['score']})"
                for idx, t in enumerate(top)
            ]
            if not reply.suggestions:
                reply.reply = (
                    "You don't have any pending tasks yet. Add a few and I'll "
                    "rank them for you."
                )

        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": reply.reply})
        return reply
