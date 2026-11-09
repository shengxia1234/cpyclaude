from __future__ import annotations

import json

from dataclasses import dataclass,field
from typing import Any

from cpy_Claude.core.llm.types import LLMResponse

_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. "
    "Use the available tools to complete the user's goal. "
    "When the goal is fully achieved, respond with a final answer and do not call any more tools."
)

@dataclass
class ExecutionContext:
    run_id : str
    goal : str
    step_max : int
    step_now : int = 0
    messages : list[dict[str,Any]] = field(default_factory=list)
    status : str = "running"
    reason : str | None = None #失败原因
    which_api : str = "anthropic"

    # 初始化历史,将用户问题放入messages中
    def __post_init__(self) -> None:
        if self.goal is not None:
            if self.which_api == "anthropic":
                self.messages.append({
                    "role" : "user",
                    "content" : self.goal
                })
            elif self.which_api == "openai":
                self.messages.append({
                    "role" : "system",
                    "content" : _SYSTEM_PROMPT
                })
                self.messages.append({
                    "role" : "user",
                    "content" : self.goal
                })

    # def add_assistant_message(self,content : list[Any]):
    #     self.messages.append({
    #         "role" : "assistant",
    #         "content" : content
    #     })

    def _add_assistant_message(self,response : LLMResponse):
        if self.which_api == "anthropic":
            blocks: list[dict[str, object]] = []
            if response.text:
                blocks.append({"type": "text","text": response.text})
            for tc in response.tool_call:
                blocks.append({"type": "tool_use","id": tc.id,"name": tc.name,"input": tc.input})
            self.messages.append({
                "role" : "assistant",
                "content" : blocks
            })
        elif self.which_api == "openai":
            tool_calls : list[dict[str,object]] | None = None
            content : str | None = None
            if response.text:
                content = response.text
            if response.tool_call:
                tool_calls = []
                for tc in response.tool_call:
                    tool_calls.append({
                        "id" : tc.id,
                        "type" : "function",
                        "function" : {
                            "name" : tc.name,
                            "arguments" : json.dumps(tc.input)
                        }
                    })
            self.messages.append({
                "role" : "assistant",
                "content" : content,
                "tool_calls" : tool_calls
            })

    # 将工具执行结果添加到发送消息中
    def add_tool_result(self,tool_id : str,content : str,is_error : bool = False):
        if self.which_api == "anthropic":
            # 注意工具调用格式
            tool_res = {
                "type" : "tool_result",
                "tool_use_id" : tool_id,
                "content" : content,
                "is_error" : is_error
            }

            last = self.messages[-1] if self.messages else None
            if(
                last is not None
                and isinstance(last["content"],list)
                and last["content"]
                and all(tmp.get("type") == "tool_result" for tmp in last["content"])
            ):
                last["content"].append(tool_res)
            else:
                self.messages.append({"role" : "user","content" : [tool_res]})
        elif self.which_api == "openai":
            tool_res = {
                "role" : "tool",
                "tool_call_id" : tool_id,
                "content" : content
            }
            self.messages.append(tool_res)

    # 检查状态是否不再是 running
    @property
    def is_done(self) -> bool:
        return self.status != "running"

    def mark_success(self):
        self.status = "success"

    def mark_failed(self,reason : str):
        self.status = "failed"
        self.reason = reason
