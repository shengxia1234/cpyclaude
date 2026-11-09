from __future__ import annotations

import datetime
import anthropic
import openai
import os
import json

from typing import Any
from cpy_Claude.core.llm.types import LLMResponse
from cpy_Claude.core.events.bus import EventBus
from cpy_Claude.core.bus.events import LLMModelSelectedEvent,LLMTokenEvent,LLMUsageEvent
from cpy_Claude.core.llm.types import ToolCallBlock,UsageForAnthropic,LLMRequestForOpenAI,UsageForOpenAI

_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. "
    "Use the available tools to complete the user's goal. "
    "When the goal is fully achieved, respond with a final answer and do not call any more tools."
)
tz = datetime.timezone(datetime.timedelta(hours=8))
# 返回当前 UTC 时间的 ISO 8601 字符串
def _now() -> str:
    return datetime.datetime.now(tz).isoformat()

class AnthropicProvider:
    def __init__(self,model : str,client : Any | None = None,BaseURL : Any | None = None):
        if client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise SystemExit("ANTHROPIC_API_KEY is not set.")
            base_url = ""
            if BaseURL is not None:
                base_url = BaseURL
            else:
                base_url = os.getenv("ANTHROPIC_BASE_URL")
            self._client = anthropic.AsyncAnthropic(api_key=api_key,base_url=base_url)
        else:
            self._client = client
        self._model = model

    async def chat(
        self,
        messages : list[dict[str,object]],
        tool_schema : list[dict[str,object]],
        bus : EventBus,
        run_id : str
    ) -> LLMResponse:
        await bus.publish(LLMModelSelectedEvent(run_id=run_id,model=self._model,strategy="static",ts=_now()))
        # 使用读取缓存，将断点前的内容进行缓存，注意内容必须完全一致才能触发缓存
        SystemPrompt : list[dict[str,object]] = [{"type":"text","text":_SYSTEM_PROMPT,"cache_control":{"type": "ephemeral"}}]
        # 浅拷贝
        tools : list[dict[str,object]] = list(tool_schema)
        if tools:
            lasttool = dict(tools[-1])
            lasttool["cache_control"] = {"type": "ephemeral"}
            tools = tools[:-1] + [lasttool]
        kwargs : dict[str,Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "system": SystemPrompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        text_parts: list[str] = []
        
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                await bus.publish(LLMTokenEvent(run_id=run_id,token=text,ts=_now()))
                text_parts.append(text)
            final_msg = await stream.get_final_message()

        usage = final_msg.usage
        # 属性可能存在但为None，所以用or
        cache_create_usage = getattr(usage,"cache_creation_input_tokens",0) or 0
        cache_read_usage = getattr(usage,"cache_read_input_tokens",0) or 0

        await bus.publish(
            LLMUsageEvent(
                run_id=run_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_creation_input_tokens=cache_create_usage,
                cache_read_input_tokens=cache_read_usage,
                ts=_now()
            )
        )
        tool_call : list[ToolCallBlock] = []
        for block in final_msg.content:
            if block.type == "tool_use":
                tool_call.append(ToolCallBlock(id=block.id,name=block.name,input=block.input))
            
        # str(list)是将列表直接转为str，join(list)则是将列表元素组合在一起变成str
        return LLMResponse(
            stop_reason=final_msg.stop_reason or "end_turn",
            tool_call=tool_call,
            text="".join(text_parts),
            usage=UsageForAnthropic(usage.input_tokens,usage.output_tokens,cache_read_usage,cache_create_usage),
        )

class OpenAIProvider:
    def __init__(self,model : str,client : Any | None = None,BaseURL : str | None = None):
        if client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise SystemExit("OPENAI_API_KEY is not set.")
            base_url = ""
            if BaseURL is not None:
                base_url = BaseURL
            else:
                base_url = os.getenv("OPENAI_BASE_URL")
            self._client = openai.AsyncOpenAI(api_key=api_key,base_url=base_url)
        else:
            self._client = client
        self._model = model

    async def chat(
        self,
        messages : list[dict[str,object]],
        tool_schema : list[dict[str,object]],
        bus : EventBus,
        run_id : str
    ) -> LLMResponse:
        await bus.publish(LLMModelSelectedEvent(run_id=run_id,model=self._model,strategy="static",ts=_now()))

        LLMMessageStruct = LLMRequestForOpenAI(
            model=self._model,
            messages=messages,
            tools=tool_schema,
            max_completion_tokens=4096,
        )
        text_parts = []

        async with self._client.chat.completions.stream(**vars(LLMMessageStruct)) as stream:
            async for chunk in stream:
                if chunk.type == "content.delta":
                    await bus.publish(LLMTokenEvent(run_id=run_id,token=chunk.delta,ts=_now()))
            text_parts = await stream.get_final_completion()

        tool_calls = text_parts.choices[0].message.tool_calls
        Tool_calls : list[ToolCallBlock] = []
        if tool_calls is not None:
            for tool_call in tool_calls:
                Tool_calls.append(ToolCallBlock(
                    tool_call.id,
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments)
                ))
        stop_reason = text_parts.choices[0].finish_reason
        text = text_parts.choices[0].message.content
        usage = text_parts.usage
        Usage = None
        if usage is not None:
            Usage = UsageForOpenAI(
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.prompt_tokens_details.cached_tokens if usage.prompt_tokens_details else None,
                usage.completion_tokens_details.reasoning_tokens if usage.completion_tokens_details else None
            )
        
        return LLMResponse(stop_reason,Tool_calls,text,Usage)