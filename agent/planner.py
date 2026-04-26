"""Study-plan builder.

Given a list of prioritized tasks the planner produces:

* a daily breakdown of what to focus on for the next *N* days, and
* a high-level workload summary that the UI surfaces as KPI cards.

The algorithm is intentionally simple so it can run without any LLM:

1.  Walk the prioritized list in score order.
2.  Pack tasks into days, respecting a configurable daily-hour budget.
3.  Tasks that are due sooner than their packed day get pulled forward.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from .prioritizer import prioritize_tasks


DEFAULT_DAILY_HOURS = 3.0
DEFAULT_HORIZON_DAYS = 7


def _today(tz: timezone = timezone.utc) -> date:
    return datetime.now(tz).date()


def _due_date(task: dict) -> Optional[date]:
    raw = task.get("due_date")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def build_study_plan(
    tasks: Iterable[dict],
    *,
    daily_hours: float = DEFAULT_DAILY_HOURS,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    start: Optional[date] = None,
) -> List[dict]:
    """Return a list of day plans covering *horizon_days* starting at *start*.

    Each entry has the shape::

        {
            "date": "2026-04-26",
            "weekday": "Sunday",
            "scheduled_hours": 2.5,
            "items": [ {task...}, ... ],
        }
    """

    start = start or _today()
    prioritized = prioritize_tasks(tasks)
    pending = [t for t in prioritized if str(t.get("status", "")).lower() != "done"]

    # Initialize empty day buckets.
    plan: List[dict] = []
    for offset in range(horizon_days):
        day = start + timedelta(days=offset)
        plan.append(
            {
                "date": day.isoformat(),
                "weekday": day.strftime("%A"),
                "scheduled_hours": 0.0,
                "remaining_hours": daily_hours,
                "items": [],
            }
        )

    for task in pending:
        effort = float(task.get("estimated_hours", 1) or 1)
        due = _due_date(task)

        # Hard deadline: cannot be scheduled later than the due date.
        last_index = horizon_days - 1
        if due is not None:
            delta = (due - start).days
            if delta < 0:
                last_index = 0  # overdue -> work on it today
            else:
                last_index = min(last_index, delta)

        placed = False
        for idx in range(last_index + 1):
            bucket = plan[idx]
            if bucket["remaining_hours"] >= effort or idx == last_index:
                bucket["items"].append(task)
                bucket["scheduled_hours"] = round(bucket["scheduled_hours"] + effort, 2)
                bucket["remaining_hours"] = round(
                    max(0.0, bucket["remaining_hours"] - effort), 2
                )
                placed = True
                break

        if not placed:  # safety net - drop into the last bucket
            plan[-1]["items"].append(task)
            plan[-1]["scheduled_hours"] += effort

    # Strip the helper field from the response.
    for bucket in plan:
        bucket.pop("remaining_hours", None)
    return plan


def summarize_workload(tasks: Iterable[dict]) -> Dict[str, float]:
    """Return KPI numbers for the dashboard cards."""

    prioritized = prioritize_tasks(tasks)
    today = _today()

    pending = [t for t in prioritized if str(t.get("status", "")).lower() != "done"]
    overdue = 0
    due_this_week = 0
    total_hours = 0.0
    critical = 0
    for task in pending:
        total_hours += float(task.get("estimated_hours", 0) or 0)
        if task.get("priority") == "critical":
            critical += 1
        due = _due_date(task)
        if due is None:
            continue
        delta = (due - today).days
        if delta < 0:
            overdue += 1
        elif delta <= 7:
            due_this_week += 1

    return {
        "total_tasks": len(list(prioritized)),
        "pending_tasks": len(pending),
        "overdue_tasks": overdue,
        "due_this_week": due_this_week,
        "critical_tasks": critical,
        "estimated_hours": round(total_hours, 1),
    }
