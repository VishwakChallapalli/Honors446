"""Unit tests for the prioritization engine."""

from datetime import datetime, timezone

from agent.prioritizer import prioritize_tasks, score_task


def test_overdue_scores_high():
    task = {
        "title": "Exam",
        "due_date": "2020-01-01",
        "weight": 10,
        "estimated_hours": 2,
        "difficulty": 3,
        "status": "pending",
    }
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    scored = score_task(task, now=now)
    assert scored.label == "critical"
    assert scored.score >= 88.0


def test_done_task_zero_score():
    task = {
        "title": "Done",
        "due_date": "2026-04-01",
        "weight": 50,
        "estimated_hours": 10,
        "status": "done",
    }
    scored = score_task(task)
    assert scored.score == 0


def test_prioritize_orders_by_score():
    tasks = [
        {"title": "Later", "due_date": "2026-12-31", "weight": 5, "estimated_hours": 1, "status": "pending"},
        {"title": "Soon", "due_date": "2026-04-26", "weight": 20, "estimated_hours": 4, "status": "pending"},
    ]
    ordered = prioritize_tasks(tasks, now=datetime(2026, 4, 25, tzinfo=timezone.utc))
    assert ordered[0]["title"] == "Soon"
