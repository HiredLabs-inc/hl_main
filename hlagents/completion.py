"""Single-shot AI tasks, such as writing a resume overview (docs/designs/completed/ai-tasks.md §3.4).

A task is one provider call with no tools: the TaskConfig's instructions as the
system prompt and the caller's text as the user message. Every call, failed or
not, is recorded as a TaskCall and counts toward the agents' daily cap.
"""
import logging

from hlagents.models import TaskCall, TaskConfig
from hlagents.providers import ChatResult, call_with_limit, get_provider
from hlagents.services import cap_problem, provider_problem

logger = logging.getLogger(__name__)

# Seconds to wait for one reply. Tasks run inside a web request, so this is
# much shorter than an agent's.
TIMEOUT = 45


class CompletionFailed(Exception):
    """The task couldn't run, or its provider failed. `model` is the configured
    model, or "" when the task isn't set up."""

    def __init__(self, model, reason):
        super().__init__(reason)
        self.model = model
        self.reason = reason


def complete(key, user_message, user=None) -> str:
    """The task's reply to `user_message`, or CompletionFailed."""
    return complete_result(key, user_message, user).message["content"]


def complete_result(key, user_message, user=None, limit=None) -> ChatResult:
    """complete() with the provider's whole result, including the sources of a
    search (docs/designs/in-progress/gcp-agents.md §3.2). `limit` is the most seconds the call may
    take (call_with_limit)."""
    config = TaskConfig.objects.select_related("provider").filter(key=key).first()
    if config is None:
        raise CompletionFailed("", f"No task is set up for {key}.")
    if problem := task_problem(config):
        _record(config, user, error=problem)
        raise CompletionFailed(config.model, problem)

    messages = [
        {"role": "system", "content": config.instructions},
        {"role": "user", "content": user_message},
    ]
    try:
        provider = get_provider(config.provider, timeout=TIMEOUT)

        def chat():
            return provider.chat(config.model, messages, tools=None, options=config.options)

        result = call_with_limit(chat, limit, config.model) if limit else chat()
    except Exception as e:
        logger.exception("Task %s failed (%s)", key, config.model)
        _record(config, user, error=f"{type(e).__name__}: {e}")
        raise CompletionFailed(config.model, str(e)) from e

    text = result.message["content"] = (result.message.get("content") or "").strip()
    _record(
        config,
        user,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        error="" if text else "The reply was empty.",
    )
    if not text:
        raise CompletionFailed(config.model, "The reply was empty.")
    # Messages hold participant data, so only sizes are logged
    logger.debug("Task %s: %d chars from a %d char message", key, len(text), len(user_message))
    return result


def task_problem(config: TaskConfig) -> str:
    """Why the task can't run right now, or ""."""
    if not config.active:
        return f"The {config} task is turned off in settings."
    return provider_problem(config.provider) or cap_problem()


def _record(config, user, input_tokens=0, output_tokens=0, error=""):
    return TaskCall.objects.create(
        config=config,
        model=config.model,
        user=user if user is not None and user.is_authenticated else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=config.provider.token_cost(input_tokens, output_tokens),
        ok=not error,
        error=error,
    )
