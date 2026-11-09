from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UsageForAnthropic:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class ToolCallBlock:
    id : str
    name : str
    input : dict[str, object]


@dataclass
class LLMResponse:
    stop_reason : str  # "end_turn" | "tool_use"
    tool_call : list[ToolCallBlock] = field(default_factory=list)
    text : str | None = ""
    usage : UsageForAnthropic | UsageForOpenAI |None = None

@dataclass
class UsageForOpenAI:
    input_tokens : int
    output_tokens : int
    cached_token : int | None = 0 # 命中了提示词缓存token数
    reasoning_token : int | None= 0 # 模型在生成回答时，内部推理过程所消耗的token数量

@dataclass
class LLMRequestForOpenAI:
    model : str
    messages : list[dict[str,object]]
    tools : list[dict[str,object]]
    max_completion_tokens : int