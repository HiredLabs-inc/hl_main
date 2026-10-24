"""Resume text written by an LLM, through the hlagents tasks (docs/ai-tasks.md).

Each function builds the user message from the participant's data; the task's
instructions, provider and model are edited in /agents/settings/.
"""
import json
import re
from typing import List

from cold_apply.models import Job, Skill
from hlagents.completion import CompletionFailed, complete
from resume.models import Bullet, Experience, Position

# How much of a job description goes into a prompt
DESCRIPTION_CHARS = 1000


class TextGenerationError(Exception):
    """The model call failed or returned no text."""


def get_keywords(job: Job):
    """Returns a list of keywords for a job description."""
    keywords = job.keywordanalysis_set.values_list("unigram", "bigram", "trigram")
    unigrams = [unigram for unigram, _, _ in keywords]
    bigrams = [bigram for _, bigram, _ in keywords]
    trigrams = [trigram for _, _, trigram in keywords]

    return unigrams, bigrams, trigrams


def _keyword_text(job: Job) -> str:
    unigrams, bigrams, trigrams = get_keywords(job)
    # Cells are blank where a row's keyword lists differ in length
    return ", ".join(phrase for phrase in unigrams + bigrams + trigrams if phrase)


def rewrite_bullet_for_job(bullet: Bullet, job: Job, user=None) -> str:
    message = f"Bullet point:\n{bullet.text}"
    if keywords := _keyword_text(job):
        message += f"\n\nKeywords from the job:\n{keywords}"
    return generate_text("bullet_rewrite", message, user)


def generate_overview(position: Position, job: Job = None, user=None) -> str:
    message = f"Job title: {position.title}"
    if job:
        if keywords := _keyword_text(job):
            message += f"\n\nKeywords from the job:\n{keywords}"
        if job.description:
            message += f"\n\nJob description:\n{job.description[:DESCRIPTION_CHARS]}"
    return generate_text("resume_overview", message, user)


def generate_bullets(experience: Experience, skills: List[Skill] = None, quantity=1, user=None) -> List[str]:
    message = f"Write {quantity} bullet point{'s' if quantity != 1 else ''} for this work experience heading:\n{experience.position.title}"
    if skills:
        skills_list = "\n".join(skill.title for skill in skills)
        message += f"\n\nFocus on these skills:\n{skills_list}"
    existing = [bullet.text for bullet in experience.bullet_set.all()]
    if existing:
        existing_list = "\n".join(existing)
        message += f"\n\nBullet points already written for this experience (don't repeat them):\n{existing_list}"

    bullets = parse_bullets(generate_text("resume_bullets", message, user))
    if not bullets:
        raise TextGenerationError(failure_message(""))
    return bullets[:quantity]


def parse_bullets(text: str) -> List[str]:
    """Bullet points from a reply: a JSON list of strings (possibly in a code
    fence), or failing that one per line, without bullet characters or numbers."""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    cleaned = (match.group(1) if match else text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list) and all(isinstance(item, str) for item in data):
        lines = data
    else:
        lines = cleaned.split("|") if "|" in cleaned and "\n" not in cleaned else cleaned.splitlines()
    bullets = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().rstrip(",").strip('"') for line in lines]
    # Brackets on their own lines are left from a JSON list that didn't parse
    return [bullet for bullet in bullets if bullet and bullet not in ("[", "]")]


def failure_message(model: str) -> str:
    return f"The LLM failed you. {model or 'It'} feels shame, but you can try again later."


def generate_text(key: str, message: str, user=None) -> str:
    """Runs the hlagents task `key` on `message`. A failure, whatever the
    cause, raises TextGenerationError with a message for the user."""
    try:
        return complete(key, message, user=user)
    except CompletionFailed as e:
        raise TextGenerationError(failure_message(e.model)) from e
