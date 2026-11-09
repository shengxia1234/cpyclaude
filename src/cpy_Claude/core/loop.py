from __future__ import annotations
import datetime
import asyncio

from cpy_Claude.core.llm.base import LLMProvider
from cpy_Claude.core.tools.registry import ToolRegistry
from cpy_Claude.core.events.bus import EventBus
from cpy_Claude.core.context import ExecutionContext
from cpy_Claude.core.bus.events import StepStartEvent,StepFinishEvent
from cpy_Claude.core.llm.provider import AnthropicProvider,OpenAIProvider
from cpy_Claude.core.tools.invocation import invoke_tool

tz = datetime.timezone(datetime.timedelta(hours=8))
# 返回当前 UTC 时间的 ISO 8601 字符串
def _now() -> str:
    return datetime.datetime.now(tz).isoformat()

class AgentLoop:
    def __init__(self,LLM : LLMProvider,tools : ToolRegistry,bus : EventBus):
        self._LLM = LLM
        self._tools = tools
        self._bus = bus

    async def loop(self,context : ExecutionContext):
        if isinstance(self._LLM,OpenAIProvider):
            tool_schema = self._tools.tool_schema_openai()
        else:
            tool_schema = self._tools.tool_schema_anthropic()

        while not context.is_done:
            context.step_now += 1
            await self._bus.publish(StepStartEvent(run_id=context.run_id,step=context.step_now,ts=_now()))
        # 发送请求
            try:
                response = await self._LLM.chat(context.messages,tool_schema,self._bus,context.run_id)
            except asyncio.CancelledError:
                context.mark_failed("cancelled")
                raise
            except Exception as e:
                context.mark_failed(f"llm_error:{e}")
                break
        # 收到回应,加入上下文
            # blocks: list[dict[str, object]] = []
            # if response.text:
            #     blocks.append({"type": "text","text": response.text})
            # for tc in response.tool_call:
            #     blocks.append({"type": "tool_use","id": tc.id,"name": tc.name,"input": tc.input})
            context._add_assistant_message(response)
        # 调用工具
            if response.stop_reason in ("tool_use","tool_calls"):
                for tool_call in response.tool_call:
                    res = await invoke_tool(tool_call,self._bus,context.run_id,self._tools)
                    context.add_tool_result(tool_call.id,res.content)
            elif response.stop_reason in ("end_turn","stop"):
                context.mark_success()
            elif context.step_now >= context.step_max:
                context.mark_failed("exceeded max step")
        # 结束
            await self._bus.publish(StepFinishEvent(run_id=context.run_id,step=context.step_now,ts=_now()))
