from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel

class ToolResult(BaseModel):
    success: bool
    data: Any
    error: str = ""

class BaseTool(ABC):
    name: str
    description: str
    requires_permission: bool = False

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        pass
