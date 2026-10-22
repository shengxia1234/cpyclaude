from __future__ import annotations
from dataclasses import dataclass,field
# 定义接收LLM消息的数据结构体

@dataclass
class UsageForAnthropic:
    input_tokens : int # 输入的token数量
    output_token : int # 输出的token数量
    cache_read_input_tokens: int = 0 # 从缓存读取的输入Token数量
    cache_creation_input_tokens: int = 0 # 创建缓存使用的输入token数量

@dataclass
class ToolCallBlockForAnthropic:
    id : str
    name : str
    input : dict[str,object]

@dataclass
class LLMResponseForAnthropic:
    stop_reason : str # "end_turn" | "tool_use"
    tool_call : list[ToolCallBlockForAnthropic] = field(default_factory=list)
    text : str = ""
    usage : UsageForAnthropic | None = None