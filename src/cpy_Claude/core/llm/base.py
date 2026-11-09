from __future__ import annotations

from typing import Protocol
from cpy_Claude.core.llm.types import LLMResponse
from cpy_Claude.core.events.bus import EventBus

# 静态鸭子类型
class LLMProvider(Protocol):
    async def chat(
        self,
        messages : list[dict[str,object]],
        tool_schema : list[dict[str,object]],
        bus : EventBus,
        run_id : str
    ) -> LLMResponse: ...