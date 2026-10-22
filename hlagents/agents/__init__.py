"""Agent types: how an agent's final reply becomes leads (docs/hlagents.md §3.1).

Prompts, models and providers live in AgentConfig rows; only parsing and
mapping are code.
"""
from .base import AgentType, ParseError
from .funding import FundingAgent
from .outreach import OutreachAgent

AGENT_TYPES = {agent.key: agent for agent in (FundingAgent(), OutreachAgent())}


def get_agent_type(key) -> AgentType:
    return AGENT_TYPES[key]


def agent_type_choices():
    return [(agent.key, agent.label) for agent in AGENT_TYPES.values()]
