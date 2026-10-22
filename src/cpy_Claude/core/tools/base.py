from __future__ import annotations

# 抽象基类
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ToolResult:
    content : str
    is_error : bool = False
    error_type : str | None = None # "runtime_error" | "timeout" | "schema_error"

class BaseTool(ABC):
    name : str
    description : str
    input_schema : dict[str,object]

    #子类必须实现
    @abstractmethod
    async def invoke(self,params : dict[str,object]) -> ToolResult:...