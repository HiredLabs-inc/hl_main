from dataclasses import dataclass
from typing import Callable


class ToolError(Exception):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    # JSON schema of the arguments
    parameters: dict
    func: Callable
