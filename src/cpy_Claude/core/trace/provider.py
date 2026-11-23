from __future__ import annotations

import datetime
import time
import dataclasses

from cpy_Claude.core.llm.base import LLMProvider
from cpy_Claude.core.llm.provider import AnthropicProvider,OpenAIProvider
from cpy_Claude.core.llm.types import LLMResponse
from cpy_Claude.core.trace.writer import TraceWriter
from cpy_Claude.core.trace.record import TraceRecord
from cpy_Claude.core.events.bus import EventBus

tz = datetime.timezone(datetime.timedelta(hours=8))
def _now() -> str:
    return datetime.datetime.now(tz).isoformat()

class TraceProvider:
    # 持有真实 provider、TraceWriter 和完整/摘要 payload 开关。
    def __init__(self,provider : LLMProvider,trace_writer : TraceWriter,include_payload : bool):
        self._inner_LLM = provider
        self._trace_writer = trace_writer
        self._include_payload = include_payload
        self.which_api : str = "anthropic" if isinstance(provider,AnthropicProvider) else "openai"

    # 记录请求，调用并透传真正的 chat 与 step，统计耗时，记录成功响应，原样返回结果。
    async def chat(
        self,
        messages : list[dict[str,object]],
        tool_schema : list[dict[str,object]],
        bus : EventBus,
        run_id : str,
        step : int = 0
    ) -> LLMResponse:
        if self._include_payload:
            call_data = {
                "messages" : messages,"tool_schema" : tool_schema
            }
        else:
            call_data = {
                "messages" : len(messages),"tool_schema" : len(tool_schema)
            }
        self._trace_writer.emit(TraceRecord(
            ts=_now(),
            direction="CORE->LLM",
            layer="llm",
            kind="api_call",
            run_id=run_id,
            step=step,
            data=call_data
        ))

        t0 = time.monotonic()
        result = await self._inner_LLM.chat(messages,tool_schema,bus,run_id,step)
        latency_ms = (time.monotonic() - t0) * 1000

        if self._include_payload:
            resp_data = {
                "stop_reason": result.stop_reason,
                "text": result.text,
                "tool_calls": [dataclasses.asdict(tc) for tc in result.tool_call],
                "usage": dataclasses.asdict(result.usage) if result.usage else {},
                "latency_ms": latency_ms,
            }
        else:
            resp_data = {
                "stop_reason": result.stop_reason,
                "usage": dataclasses.asdict(result.usage) if result.usage else {},
                "latency_ms": latency_ms,
            }
        self._trace_writer.emit(TraceRecord(
            ts=_now(),
            direction="CORE->LLM",
            layer="llm",
            kind="api_response",
            run_id=run_id,
            step=step,
            data=resp_data
        ))
        return result

