"""Job description keywords, from an LLM through the hlagents job_keywords task,
with the in-house analyzer as the fallback (docs/ai-tasks.md §3.6).

Keywords are stored as KeywordAnalysis rows that pair the i-th unigram, bigram
and trigram. LLM lists differ in length (three-word phrases are scarce), so the
shorter lists leave blank cells rather than dropping the others' keywords.
"""
import json
import logging
import re
from itertools import zip_longest

from django.db import transaction

from cold_apply.models import Job, KeywordAnalysis
from hlagents.completion import CompletionFailed, complete

from .static.scripts.keyword_analyzer.keyword_analyzer import analyze

logger = logging.getLogger(__name__)

TASK = "job_keywords"
# The reply's keys, the KeywordAnalysis field each fills, and its word count
LISTS = (("unigrams", "unigram", 1), ("bigrams", "bigram", 2), ("trigrams", "trigram", 3))
MOST_PER_LIST = 20
# KeywordAnalysis fields are CharField(max_length=200)
MAX_PHRASE_CHARS = 200
# Punctuation that separates words without being part of them, e.g. "Python, Java (AWS)"
SEPARATORS = re.compile(r"[\s,;:()\[\]\"“”]+")


class KeywordError(ValueError):
    """The LLM's reply couldn't be used."""


def extract_keywords(job: Job, user=None) -> str:
    """Replace the job's keywords. Returns "llm", or "fallback" when the task
    failed or its reply couldn't be used and the in-house analyzer ran."""
    source = "llm"
    try:
        if not job.description.strip():
            raise KeywordError("The job has no description.")
        keywords = llm_keywords(job.description, user)
    except (CompletionFailed, KeywordError) as e:
        logger.warning("Job %s keywords fell back to the in-house analyzer: %s", job.pk, e)
        keywords = fallback_keywords(job.description)
        source = "fallback"
    save_keywords(job, keywords)
    return source


def llm_keywords(description: str, user=None) -> dict:
    """{"unigram": [...], "bigram": [...], "trigram": [...]} from the job_keywords
    task, keeping only phrases with the right word count that appear in the
    description. Raises CompletionFailed, or KeywordError if nothing is usable."""
    keywords = usable_phrases(parse_reply(complete(TASK, description, user=user)), description)
    if not any(keywords.values()):
        raise KeywordError("No usable keywords in the reply.")
    return keywords


def usable_phrases(data: dict, description: str) -> dict:
    """The reply's lists by KeywordAnalysis field, without phrases that have the
    wrong word count, are too long, repeat, or aren't in the description."""
    text = _normalize(description)
    keywords = {}
    for key, field, words in LISTS:
        phrases, seen = [], set()
        for phrase in data.get(key) or []:
            phrase = _normalize(str(phrase))
            if (
                len(phrase.split()) == words
                and len(phrase) <= MAX_PHRASE_CHARS
                and phrase.lower() not in seen
                and _appears_in(phrase, text)
            ):
                seen.add(phrase.lower())
                phrases.append(phrase)
        keywords[field] = phrases[:MOST_PER_LIST]
    return keywords


def parse_reply(reply: str) -> dict:
    """The reply's JSON object, possibly in a code fence."""
    match = re.search(r"```(?:json)?\s*(.*?)```", reply, re.DOTALL)
    try:
        data = json.loads((match.group(1) if match else reply).strip())
    except json.JSONDecodeError as e:
        raise KeywordError(f"The reply isn't valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise KeywordError("The reply isn't a JSON object.")
    return data


def fallback_keywords(description: str) -> dict:
    """The in-house analyzer's keywords, in the same shape as llm_keywords."""
    rows = json.loads(analyze(description)).values()
    return {field: [row[field] for row in rows] for _, field, _ in LISTS}


def save_keywords(job: Job, keywords: dict):
    rows = zip_longest(*(keywords[field] for _, field, _ in LISTS), fillvalue="")
    with transaction.atomic():
        KeywordAnalysis.objects.filter(job=job).delete()
        KeywordAnalysis.objects.bulk_create(
            KeywordAnalysis(job=job, unigram=unigram, bigram=bigram, trigram=trigram)
            for unigram, bigram, trigram in rows
        )


def _normalize(text: str) -> str:
    return SEPARATORS.sub(" ", text).strip()


def _appears_in(phrase: str, text: str) -> bool:
    """Whether the phrase is in the (normalized) text as whole words, ignoring case."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE) is not None
