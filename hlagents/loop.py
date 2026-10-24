"""Runs an agent until it gives a final answer (docs/hlagents.md §3.1, §3.8).

Ported from examples/utils/agent_loop.py. Messages are saved after every turn,
so the run page shows progress and a crash keeps the history.
"""
import json
import logging
import time

from django.conf import settings

from hlagents import services
from hlagents.agents import ParseError
from hlagents.conversation import note
from hlagents.models import AgentLimits, AgentRun, spent_today
from hlagents.providers import ChatProvider, get_provider
from hlagents.tools import TOOLS, tool_schema

logger = logging.getLogger(__name__)


WRAP_UP = "You're at the step limit. Give your final answer now, with what you've found so far."
RETRY = "Your reply wasn't a valid JSON list ({error}). Reply with only the JSON list."
CORRECT = (
    "These candidates weren't saved:\n{rejected}\n\n"
    "\"not in sources\" means the URL or email isn't in anything your tools returned, so it may be wrong; "
    "\"home page\" means the URL isn't a specific program's page; \"listing or news site\" means the URL is a grant "
    "listing, news story or press release, not the funder's own program page; \"shared mailbox\" means the address "
    "isn't a person's. Fix or replace them using your tools, and answer with only the fixed or new candidates, "
    "in the same JSON format. Return [] if you can't."
)


def run_agent(run: AgentRun, provider: ChatProvider = None) -> AgentRun:
    """Continue the run from its last message, then save the leads it finds.

    A reply that isn't valid JSON is sent back once to be fixed. Candidates that
    fail the agent's checks are sent back once to be fixed or replaced."""
    config = run.config
    agent = config.agent()
    tool_names = [name for name in config.tools if name in agent.allowed_tools and name in TOOLS]
    tools = [tool_schema(name, config.tool_descriptions.get(name)) for name in tool_names]

    run.status = AgentRun.Status.RUNNING
    run.error = ""
    run.save()
    saved = services.SaveResult()
    try:
        turn = _Turn(run, provider or get_provider(run.provider), tools, tool_names)
        retried = corrected = False
        while message := turn.converse():
            try:
                candidates = agent.parse(message.get("content", ""))
            except ParseError as e:
                if retried or not turn.steps_left():
                    raise
                retried = True
                run.messages.append(note(RETRY.format(error=e), "Fix the JSON"))
                continue
            result = services.save_leads(run, candidates)
            saved.add(result)
            # A correction needs a step to look things up and one to answer
            if result.rejected and not corrected and turn.steps_left() >= 2:
                corrected = True
                rejected = "\n".join(f"- {json.dumps(c)}: {reason}" for c, reason in result.rejected)
                run.messages.append(note(CORRECT.format(rejected=rejected), "Fix rejected candidates"))
                continue
            run.status = AgentRun.Status.DONE
            break
    except ParseError as e:
        run.status = AgentRun.Status.FAILED
        run.error = str(e)
    except Exception as e:
        logger.exception("Agent run %s failed", run.pk)
        run.status = AgentRun.Status.FAILED
        run.error = str(e) or e.__class__.__name__
    # A turn cut short after a first answer still reports the leads it saved
    if saved.inserted or saved.skipped:
        run.result = saved.summary()
    run.save()
    return run


class _Turn:
    """One turn of a run: the replies to a request or follow-up, which share the
    step and time limits."""

    def __init__(self, run, provider, tools, tool_names):
        self.run = run
        self.provider = provider
        self.tools = tools
        self.tool_names = tool_names
        self.limits = AgentLimits.get()
        self.deadline = time.monotonic() + settings.HLAGENTS_RUN_TIME_LIMIT
        self.steps = 0

    def steps_left(self):
        return self.run.config.max_iterations - self.steps

    def converse(self):
        """Chat until a reply has no tool calls, and return that reply. Returns
        None if the run stopped first (cap, step or time limit), with its status
        set. The last step is offered no tools, so the agent answers with what
        it has."""
        run = self.run
        while True:
            if run.cost >= self.limits.run_cost_cap or spent_today() >= self.limits.daily_cost_cap:
                return _stop(run, AgentRun.Status.CAPPED, "Stopped at the cost cap.")
            if self.steps >= run.config.max_iterations:
                return _stop(run, AgentRun.Status.FAILED, f"Stopped after {self.steps} steps without a final answer.")
            if time.monotonic() > self.deadline:
                return _stop(run, AgentRun.Status.FAILED, "Stopped at the time limit without a final answer.")

            wrap_up = bool(self.tools) and self.steps == run.config.max_iterations - 1
            if wrap_up:
                run.messages.append(note(WRAP_UP, "Step limit"))
            result = self.provider.chat(model=run.model, messages=run.messages, tools=[] if wrap_up else self.tools)
            self.steps += 1
            run.iterations += 1
            run.input_tokens += result.input_tokens
            run.output_tokens += result.output_tokens
            run.cost += run.provider.token_cost(result.input_tokens, result.output_tokens)
            run.messages.append(result.message)

            calls = result.message.get("tool_calls")
            if calls and wrap_up:
                # Some models call tools even when none are offered; take the reply as its answer
                result.message.pop("tool_calls")
                calls = None
            if not calls:
                run.save()
                return result.message

            for call in calls:
                name = call["function"]["name"]
                output = _call_tool(name, call["function"].get("arguments") or {}, self.tool_names)
                run.tool_calls += 1
                run.cost += self.limits.tool_cost(name)
                run.messages.append({"role": "tool", "tool_name": name, "content": json.dumps(output, default=str)})
            run.save()


def _call_tool(name, arguments, tool_names):
    """The tool's output, or an error the model can read and recover from."""
    if name not in tool_names:
        return {"error": f"There is no tool named {name}."}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return {"error": "The arguments aren't valid JSON."}
    try:
        return TOOLS[name].func(**arguments)
    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return {"error": str(e) or e.__class__.__name__}


def _stop(run, status, error):
    run.status = status
    run.error = error
    run.save()
    return None
