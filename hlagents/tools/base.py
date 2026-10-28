from dataclasses import dataclass
from typing import Callable


class ToolError(Exception):
    pass


# The key of a tool output that's for the run page, not the model: Google's
# search suggestions, which its terms ask us to show with grounded results
SUGGESTIONS = "suggestions"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    # JSON schema of the arguments
    parameters: dict
    func: Callable
    # Added after the description, even when an agent overrides it, because the
    # model needs it to use the tool well
    note: str = ""
