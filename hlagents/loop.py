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
from hlagents.models import AgentLimits, AgentRun
from hlagents.providers import ChatProvider, get_provider
from hlagents.tools import TOOLS, tool_schema

logger = logging.getLogger(__name__)


def run_agent(run: AgentRun, provider: ChatProvider = None) -> AgentRun:
    """Continue the run from its last message, then save the leads it finds."""
    config = run.config
    agent = config.agent()
    tool_names = [name for name in config.tools if name in agent.allowed_tools and name in TOOLS]
    tools = [tool_schema(name, config.tool_descriptions.get(name)) for name in tool_names]
    limits = AgentLimits.get()

    run.status = AgentRun.Status.RUNNING
    run.error = ""
    run.save()
    try:
        provider = provider or get_provider(run.provider)
        deadline = time.monotonic() + settings.HLAGENTS_RUN_TIME_LIMIT
        message = _converse(run, provider, tools, tool_names, limits, deadline)
        if message is None:
            return run
        inserted, skipped = services.save_leads(run, agent.parse(message.get("content", "")))
        run.result = f"Inserted {inserted}, skipped {skipped} (duplicate or incomplete)."
        run.status = AgentRun.Status.DONE
    except ParseError as e:
        run.status = AgentRun.Status.FAILED
        run.error = str(e)
    except Exception as e:
        logger.exception("Agent run %s failed", run.pk)
        run.status = AgentRun.Status.FAILED
        run.error = str(e) or e.__class__.__name__
    run.save()
    return run


def _converse(run, provider, tools, tool_names, limits, deadline):
    """Chat until a reply has no tool calls, and return that reply. Returns None
    if the run stopped first (cap, step or time limit), with its status set."""
    steps = 0
    while True:
        if run.cost >= limits.run_cost_cap or AgentRun.spent_today() >= limits.daily_cost_cap:
            return _stop(run, AgentRun.Status.CAPPED, "Stopped at the cost cap.")
        if steps >= run.config.max_iterations:
            return _stop(run, AgentRun.Status.FAILED, f"Stopped after {steps} steps without a final answer.")
        if time.monotonic() > deadline:
            return _stop(run, AgentRun.Status.FAILED, "Stopped at the time limit without a final answer.")

        result = provider.chat(model=run.model, messages=run.messages, tools=tools)
        steps += 1
        run.iterations += 1
        run.input_tokens += result.input_tokens
        run.output_tokens += result.output_tokens
        run.cost += run.provider.token_cost(result.input_tokens, result.output_tokens)
        run.messages.append(result.message)

        calls = result.message.get("tool_calls")
        if not calls:
            run.save()
            return result.message

        for call in calls:
            name = call["function"]["name"]
            output = _call_tool(name, call["function"].get("arguments") or {}, tool_names)
            run.tool_calls += 1
            run.cost += limits.tool_cost(name)
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
