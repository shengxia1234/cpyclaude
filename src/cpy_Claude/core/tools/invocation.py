import datetime
import time
import asyncio

from typing import cast

from cpy_Claude.core.events.bus import EventBus
from cpy_Claude.core.llm.types import ToolCallBlockForAnthropic
from cpy_Claude.core.tools.base import ToolResult
from cpy_Claude.core.bus.events import ToolCallFailEvent,ToolCallFinishEvent,ToolCallStartEvent
from cpy_Claude.core.tools.registry import ToolRegistry

_DEFAULT_TIMEOUT: float = 10.0
tz = datetime.timezone(datetime.timedelta(hours=8))

def _now() -> str:
    return datetime.datetime.now(tz).isoformat()

# 发布工具调用错误事件,并返回ToolResult
async def notify_toolfail(
    bus : EventBus,
    run_id : str,
    error_type : str,
    error_msg : str,
    tool_call : ToolCallBlockForAnthropic,
    elapsed_ms : int
) -> ToolResult:
    await bus.publish(ToolCallFailEvent(
        run_id=run_id,
        tool_id=tool_call.id,
        tool_name=tool_call.name,
        error_type=error_type,
        error_msg=error_msg,
        elapsed_ms=elapsed_ms,
        ts=_now()
    ))
    return ToolResult(error_msg,True,error_type)

async def invoke_tool(
    tool_call : ToolCallBlockForAnthropic,
    bus : EventBus,
    run_id : str,
    elapsed_ms : int,
    tools : ToolRegistry
) -> ToolResult:
    t0 = time.monotonic()
    await bus.publish(ToolCallStartEvent(
        run_id=run_id,
        tool_id=tool_call.id,
        tool_name=tool_call.name,
        params=tool_call.input,
        ts=_now()
    ))

    def elapsed() -> int:
            return int((time.monotonic() - t0) * 1000)
    tool = tools.get(tool_call.name)
    if tool is None:
        return await notify_toolfail(bus,run_id,"runtime_error",f"unknown tool:{tool_call.name}",tool_call,elapsed())

    required : list[str] = cast(list[str],tool.input_schema.get("required",[]))
    #检查缺失参数
    missing = [param for param in required if param not in tool_call.input]
    if missing:
        return await notify_toolfail(bus,run_id,"runtime_error",f"missing parameters:{",".join(missing)}",tool_call,elapsed())

    #检查意外参数
    unexpected = [param for param in tool_call.input if param not in required]
    if unexpected:
        return await notify_toolfail(bus,run_id,"runtime_error",f"unexpected parameters:{",".join(unexpected)}",tool_call,elapsed())

    try:
        # dict强制转换以进行防御性拷贝
        result = await asyncio.wait_for(tool.invoke(dict(tool_call.input)),timeout=_DEFAULT_TIMEOUT)
        if result.is_error:
            return await notify_toolfail(bus,run_id,result.error_type or "runtime_error",result.content,tool_call,elapsed())
        await bus.publish(ToolCallFinishEvent(
            run_id = run_id,
            tool_id=tool_call.id,
            tool_name=tool_call.name,
            elapsed_ms=elapsed(),
            ts=_now()
        ))
        return result
    except TimeoutError:
        return await notify_toolfail(bus,run_id,"time_out",f"Timeout:{_DEFAULT_TIMEOUT}s",tool_call,elapsed())
    except Exception as exc:
        return await notify_toolfail(bus,run_id,"runtime_error",str(exc),tool_call,elapsed())