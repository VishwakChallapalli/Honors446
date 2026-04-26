"""Flask web application for the Student Academic Productivity Agent.

This module wires together the AI agent package, a small JSON-backed task
store, and a single-page HTML front-end.  Run it with:

    python app.py

then open http://127.0.0.1:5000 in your browser.

The application is the deliverable for the Spring 2026 CSE 446 Barrett Honors
Enrichment Project (Option 2 - Low-Code Application Development using Google
Antigravity IDE).  It demonstrates an AI-driven low-code style agent that can
be authored visually in Antigravity and re-implemented programmatically here.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # python-dotenv is optional
    pass

from agent import (
    ConversationAgent,
    build_study_plan,
    prioritize_tasks,
    summarize_workload,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
TASKS_FILE = DATA_DIR / "tasks.json"

_lock = threading.Lock()
_conversation = ConversationAgent()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _seed_sample_tasks() -> List[dict]:
    """Return a small sample workload used for demos and first-run UX."""

    today = datetime.now(timezone.utc).date()
    from datetime import timedelta

    samples = [
        {
            "title": "Finish CSE 446 honors project prototype",
            "course": "CSE446",
            "due_date": (today + timedelta(days=2)).isoformat(),
            "estimated_hours": 5,
            "weight": 25,
            "difficulty": 4,
            "notes": "Wire up the agent UI and run end-to-end tests.",
            "status": "in_progress",
        },
        {
            "title": "Linear algebra problem set 7",
            "course": "MAT343",
            "due_date": (today + timedelta(days=4)).isoformat(),
            "estimated_hours": 3,
            "weight": 8,
            "difficulty": 3,
            "notes": "Eigenvalues and diagonalization.",
            "status": "pending",
        },
        {
            "title": "Read distributed systems chapter 9",
            "course": "CSE445",
            "due_date": (today + timedelta(days=6)).isoformat(),
            "estimated_hours": 2,
            "weight": 5,
            "difficulty": 2,
            "notes": "Prep for next week's quiz.",
            "status": "pending",
        },
        {
            "title": "ENG 102 persuasive essay draft",
            "course": "ENG102",
            "due_date": (today + timedelta(days=9)).isoformat(),
            "estimated_hours": 4,
            "weight": 15,
            "difficulty": 3,
            "notes": "Outline + rough draft.",
            "status": "pending",
        },
    ]
    return [{"id": str(uuid.uuid4()), **task} for task in samples]


def load_tasks() -> List[dict]:
    with _lock:
        if not TASKS_FILE.exists():
            tasks = _seed_sample_tasks()
            TASKS_FILE.write_text(json.dumps(tasks, indent=2))
            return tasks
        try:
            return json.loads(TASKS_FILE.read_text() or "[]")
        except json.JSONDecodeError:
            return []


def save_tasks(tasks: List[dict]) -> None:
    with _lock:
        TASKS_FILE.write_text(json.dumps(tasks, indent=2))


def _normalize_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate / coerce a task dictionary coming from the client or agent."""

    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("Task title is required")

    def _maybe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _maybe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    return {
        "id": payload.get("id") or str(uuid.uuid4()),
        "title": title[:140],
        "course": (payload.get("course") or "General").strip()[:40],
        "due_date": (payload.get("due_date") or "")[:10] or None,
        "estimated_hours": max(0.25, _maybe_float(payload.get("estimated_hours"), 1.0)),
        "weight": max(0.0, min(100.0, _maybe_float(payload.get("weight"), 10.0))),
        "difficulty": max(1, min(5, _maybe_int(payload.get("difficulty"), 3))),
        "notes": (payload.get("notes") or "").strip()[:500],
        "status": (payload.get("status") or "pending").lower(),
        "created_at": payload.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/tasks")
    def get_tasks():
        tasks = load_tasks()
        return jsonify(
            {
                "tasks": prioritize_tasks(tasks),
                "summary": summarize_workload(tasks),
            }
        )

    @app.post("/api/tasks")
    def create_task():
        try:
            task = _normalize_task(request.get_json(force=True) or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        tasks = load_tasks()
        tasks.append(task)
        save_tasks(tasks)
        return jsonify({"task": task}), 201

    @app.put("/api/tasks/<task_id>")
    def update_task(task_id: str):
        payload = request.get_json(force=True) or {}
        tasks = load_tasks()
        for idx, task in enumerate(tasks):
            if task.get("id") == task_id:
                merged = {**task, **payload, "id": task_id}
                tasks[idx] = _normalize_task(merged)
                save_tasks(tasks)
                return jsonify({"task": tasks[idx]})
        return jsonify({"error": "Task not found"}), 404

    @app.delete("/api/tasks/<task_id>")
    def delete_task(task_id: str):
        tasks = load_tasks()
        new_tasks = [t for t in tasks if t.get("id") != task_id]
        if len(new_tasks) == len(tasks):
            return jsonify({"error": "Task not found"}), 404
        save_tasks(new_tasks)
        return jsonify({"ok": True})

    @app.post("/api/tasks/reset")
    def reset_tasks():
        tasks = _seed_sample_tasks()
        save_tasks(tasks)
        _conversation.reset()
        return jsonify({"tasks": prioritize_tasks(tasks)})

    @app.get("/api/plan")
    def get_plan():
        tasks = load_tasks()
        return jsonify(
            {
                "plan": build_study_plan(tasks),
                "summary": summarize_workload(tasks),
            }
        )

    @app.post("/api/agent")
    def agent_endpoint():
        payload = request.get_json(force=True) or {}
        message = payload.get("message", "")
        tasks = load_tasks()
        reply = _conversation.handle(message, tasks)

        if reply.intent == "create_task" and reply.task:
            try:
                normalized = _normalize_task(reply.task)
                tasks.append(normalized)
                save_tasks(tasks)
                reply.task = normalized
            except ValueError:
                reply.task = None
                reply.reply = "I couldn't capture that task - try giving it a clear title."

        return jsonify(
            {
                "agent": reply.to_dict(),
                "tasks": prioritize_tasks(tasks),
                "summary": summarize_workload(tasks),
            }
        )

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "openai": bool(os.environ.get("OPENAI_API_KEY"))})

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") not in {"0", "false", "False", ""}
    app.run(host="127.0.0.1", port=5000, debug=debug)
