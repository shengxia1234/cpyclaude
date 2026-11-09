from __future__ import annotations

from typing import Annotated, Any, Literal,Union

from pydantic import BaseModel, Discriminator

class BaseEvent(BaseModel):
    type : Literal[""]

# Core启动事件
class CoreStartEvent(BaseEvent):
    type : Literal["core.started"] = "core.started"
    listen_addr : str
    version : str

# Agent任务开始事件
class RunStartEvent(BaseEvent):
    type : Literal["run.start"] = "run.start"
    run_id : str
    goal : str
    ts : str # time

# Agent任务结束事件
class RunFinishEvent(BaseEvent):
    type : Literal["run.finish"] = "run.finish"
    run_id : str
    status : str
    reason : str | None = None
    step : int
    ts : str # time

# 一轮执行开始事件
class StepStartEvent(BaseEvent):
    type : Literal["step.start"] = "step.start"
    run_id : str
    step : int
    ts : str # time

# 一轮执行结束事件
class StepFinishEvent(BaseEvent):
    type : Literal["step.finish"] = "step.finish"
    run_id : str
    step : int
    ts : str # time

# 工具调用开始事件
class ToolCallStartEvent(BaseEvent):
    type : Literal["tool.call_start"] = "tool.call_start"
    run_id : str
    tool_id : str
    tool_name : str
    params : dict[str,Any]
    ts : str # time

# 工具调用结束事件
class ToolCallFinishEvent(BaseEvent):
    type : Literal["tool.call_finish"] = "tool.call_finish"
    run_id : str
    tool_id : str
    tool_name : str
    elapsed_ms : int # 经过的时间
    ts : str

# 工具调用失败事件
class ToolCallFailEvent(BaseEvent):
    type : Literal["tool.call_fail"] = "tool.call_fail"
    run_id : str
    tool_id : str
    tool_name : str
    error_type : str
    error_msg : str
    elapsed_ms : int
    ts : str

# 记录LLM输出文本增量
class LLMTokenEvent(BaseEvent):
    type: Literal["llm.token"] = "llm.token"
    run_id: str
    token: str
    ts: str

# 记录token消耗
class LLMUsageEvent(BaseEvent):
    type: Literal["llm.usage"] = "llm.usage"
    run_id: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    ts: str

# 模型选择事件
class LLMModelSelectedEvent(BaseEvent):
    type: Literal["llm.model_selected"] = "llm.model_selected"
    run_id: str
    model: str
    strategy: str  # "static" | "rule_based" | "cost_budget"
    ts: str

# 通用结构化日志事件
class LogLineEvent(BaseEvent):
    type: Literal["log.line"] = "log.line"
    run_id: str
    level: str  # "DEBUG" | "INFO" | "WARNING" | "ERROR"
    source: str
    message: str
    ts: str

# 联合类型
Event = Annotated[
    Union[
        CoreStartEvent,
        RunStartEvent,
        RunFinishEvent,
        StepStartEvent,
        StepFinishEvent,
        ToolCallStartEvent,
        ToolCallFinishEvent,
        ToolCallFailEvent,
        LLMTokenEvent,
        LLMUsageEvent,
        LLMModelSelectedEvent,
        LogLineEvent
    ],
    Discriminator("type")
]