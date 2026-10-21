from .system_prompts.outreach_agent_system_prompt import outreach_agent_system_prompt as oasp
from .system_prompts.funding_agent_system_prompt import funding_agent_system_prompt as fasp

outreach_agent_messages = [
        {"role": "system", "content": oasp},
        {"role": "user", "content": "Find 10 veteran-serving organizations for outreach partnerships."}
    ]

funding_agent_messages = [
        {"role": "system", "content": fasp},
        {"role": "user", "content": "Find up to 10 funding opportunities for a non-profit."}
    ]