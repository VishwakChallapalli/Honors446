# StudyPilot

**StudyPilot** is a small web application for the CSE 446 Barrett Honors enrichment track (Option 2: low-code / AI agent style productivity tooling). It helps students capture assignments, prioritize them with a transparent scoring model, preview a seven-day study plan, and chat with an agent that understands plain-language task descriptions.

## Features

- **Dashboard** — KPIs (pending, overdue, due this week, estimated hours) and top prioritized tasks.
- **Tasks** — Create, edit, delete, and filter tasks; change status (pending / in progress / done).
- **Study plan** — Deterministic planner that spreads work across the next week using priority and due dates.
- **AI agent** — Chat panel that parses natural language into tasks, answers “what should I work on first?”, and can return a weekly plan. With `OPENAI_API_KEY` set, responses use the OpenAI API; otherwise a built-in rule-based parser keeps everything runnable offline.

## Requirements

- Python 3.10+ (tested on 3.13)
- Dependencies listed in `requirements.txt`

## Quick start

```bash
cd Honors446
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional: add OPENAI_API_KEY
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

On first run, the app seeds sample tasks under `data/tasks.json` (that file is gitignored so local data is not committed).

## Configuration

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Enables LLM-backed chat; omit for rule-based mode. |
| `OPENAI_MODEL` | Defaults to `gpt-4o-mini`. |
| `FLASK_DEBUG` | Set to `1` for Flask debug (optional). |

## Testing

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -q
```

## API (reference)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/tasks` | Prioritized tasks and summary. |
| `POST` | `/api/tasks` | Create a task (JSON body). |
| `PUT` | `/api/tasks/<id>` | Update a task. |
| `DELETE` | `/api/tasks/<id>` | Delete a task. |
| `POST` | `/api/tasks/reset` | Restore demo seed data. |
| `GET` | `/api/plan` | Seven-day study plan + summary. |
| `POST` | `/api/agent` | `{ "message": "..." }` — agent turn. |
| `GET` | `/api/health` | `{ "status", "openai" }`. |

## Project layout

```
Honors446/
├── app.py                 # Flask app
├── agent/                 # Prioritizer, planner, conversation agent
├── templates/
│   └── index.html
├── static/
│   ├── css/styles.css
│   └── js/app.js
├── tests/
│   └── test_prioritizer.py
├── data/                  # tasks.json created at runtime (ignored)
├── requirements.txt
├── .env.example
└── SUBMISSION.txt         # Short honors submission notes
```

## License and course use

This project was built for an academic honors contract. Adapt or cite it per your instructor’s policy.

## Author

Vishwak Challapalli — CSE 446, Spring 2026.
