"""Agent types: how an agent's final reply becomes leads (docs/designs/completed/hlagents.md §3.1).

Prompts, models and providers live in AgentConfig rows; only parsing and
mapping are code.
"""
from .base import CORRECTABLE, DUPLICATE, INCOMPLETE, AgentType, ParseError
from .funding import FundingAgent
from .outreach import OutreachAgent

AGENT_TYPES = {agent.key: agent for agent in (FundingAgent(), OutreachAgent())}


def get_agent_type(key) -> AgentType:
    return AGENT_TYPES[key]


def agent_for_lead_kind(kind) -> AgentType:
    return next(agent for agent in AGENT_TYPES.values() if agent.lead_kind == kind)


def agent_type_choices():
    return [(agent.key, agent.label) for agent in AGENT_TYPES.values()]
