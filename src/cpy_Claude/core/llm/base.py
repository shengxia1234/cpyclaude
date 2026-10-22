from __future__ import annotations

from typing import Protocol
from cpy_Claude.core.llm.types import LLMResponseForAnthropic

class LLMProviderForAnthropic(Protocol):
    def chat(
        self,
        messages : dict[str,object],
        tool_schema : dict[str,object],
        bus : ...,
        run_id : str
    ) -> LLMResponseForAnthropic: ...