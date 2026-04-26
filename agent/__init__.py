"""AI agent package for the Student Academic Productivity & Planning Agent.

The package is organized into three cooperating modules:

* :mod:`agent.prioritizer` - deterministic scoring for task urgency.
* :mod:`agent.planner`     - turns prioritized tasks into a study plan.
* :mod:`agent.conversation`- conversational layer that parses natural-language
  user input into structured task records.

The conversation layer prefers OpenAI when an API key is supplied, otherwise it
falls back to the rule-based parser so the project stays runnable offline.
"""

from .prioritizer import prioritize_tasks, score_task
from .planner import build_study_plan, summarize_workload
from .conversation import AgentReply, ConversationAgent

__all__ = [
    "prioritize_tasks",
    "score_task",
    "build_study_plan",
    "summarize_workload",
    "AgentReply",
    "ConversationAgent",
]
