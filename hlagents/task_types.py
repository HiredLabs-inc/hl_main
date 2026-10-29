"""Single-shot AI tasks other apps run through a provider (docs/ai-tasks.md §3).

Each key has one TaskConfig row, which staff edit in /agents/settings/.
"""

TASKS = {
    "resume_overview": "Resume overview",
    "resume_bullets": "Resume bullet points",
    "bullet_rewrite": "Bullet rewrite for a job",
    "job_keywords": "Job description keywords",
    # Behind the agents' web_search tool (docs/gcp-agents.md §3.2)
    "web_search": "Web search for agents",
}


def task_choices():
    return list(TASKS.items())
