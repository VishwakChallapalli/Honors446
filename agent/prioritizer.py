"""Task prioritization engine.

The prioritizer assigns every task a numeric ``score`` between 0 and 100 that
captures how urgent it should feel for the student.  The score is a weighted
combination of three signals:

* **Deadline pressure** - how soon the task is due.
* **Weight / impact**   - how many points or how important the task is.
* **Estimated effort**  - how many hours the student needs to invest.

A small "difficulty" multiplier lets users bump up tasks that they personally
find hard.  The function is deterministic so it works without any external API
and is easy to unit test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional


_PRIORITY_LABELS = (
    (80, "critical"),
    (60, "high"),
    (35, "medium"),
    (0, "low"),
)


@dataclass
class ScoredTask:
    """A task enriched with a priority score and human readable label."""

    task: dict
    score: float
    label: str
    days_until_due: Optional[float]

    def to_dict(self) -> dict:
        enriched = dict(self.task)
        enriched["score"] = round(self.score, 1)
        enriched["priority"] = self.label
        enriched["days_until_due"] = (
            round(self.days_until_due, 2) if self.days_until_due is not None else None
        )
        return enriched


def _parse_deadline(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        # Accept both ``YYYY-MM-DD`` and full ISO timestamps.
        if len(raw) == 10:
            return datetime.fromisoformat(raw + "T23:59:00").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _deadline_pressure(days_until_due: Optional[float]) -> float:
    """Map "days until due" onto a 0-100 urgency curve."""

    if days_until_due is None:
        return 25.0  # unknown deadline => mild urgency
    if days_until_due <= 0:
        return 100.0
    if days_until_due <= 1:
        return 95.0
    if days_until_due <= 2:
        return 85.0
    if days_until_due <= 4:
        return 70.0
    if days_until_due <= 7:
        return 55.0
    if days_until_due <= 14:
        return 35.0
    return 15.0


def _label_for(score: float) -> str:
    for threshold, label in _PRIORITY_LABELS:
        if score >= threshold:
            return label
    return "low"


def score_task(task: dict, *, now: Optional[datetime] = None) -> ScoredTask:
    """Return a :class:`ScoredTask` for a single task dictionary."""

    now = now or datetime.now(timezone.utc)
    deadline = _parse_deadline(task.get("due_date"))
    days_until_due: Optional[float]
    if deadline is None:
        days_until_due = None
    else:
        days_until_due = (deadline - now).total_seconds() / 86400.0

    weight = float(task.get("weight", 10) or 10)          # 0 - 100 (% of grade)
    effort = float(task.get("estimated_hours", 2) or 2)   # hours
    difficulty = float(task.get("difficulty", 3) or 3)    # 1-5 self-rating

    pressure = _deadline_pressure(days_until_due)
    weight_component = min(weight, 50) * 1.2              # cap influence at 60
    effort_component = min(effort, 20) * 1.5              # cap influence at 30
    difficulty_multiplier = 0.85 + (difficulty / 10.0)    # 0.95 - 1.35

    raw_score = (pressure * 0.6) + (weight_component * 0.25) + (effort_component * 0.15)
    score = max(0.0, min(100.0, raw_score * difficulty_multiplier))

    if str(task.get("status", "")).lower() in {"done", "complete", "completed"}:
        score = 0.0
    elif days_until_due is not None and days_until_due < 0:
        # Anything past its due date should surface as critical work.
        score = min(100.0, max(score, 88.0))

    return ScoredTask(
        task=task,
        score=score,
        label=_label_for(score),
        days_until_due=days_until_due,
    )


def prioritize_tasks(
    tasks: Iterable[dict], *, now: Optional[datetime] = None
) -> List[dict]:
    """Score and sort *tasks*; returns a new list of enriched dictionaries."""

    scored = [score_task(task, now=now) for task in tasks]
    scored.sort(key=lambda item: item.score, reverse=True)
    return [item.to_dict() for item in scored]
