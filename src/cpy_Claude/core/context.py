from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any

@dataclass
class ExecutionContext:
    run_id : str
    goal : str
    step_max : int
    step_now : int = 0
    messages : list[dict[str,Any]] = field(default_factory=list)
    status : str = "running"
    reason : str | None = None #失败原因

    # 初始化历史,将用户问题放入messages中
    def __post_init__(self) -> None:
        if self.goal is not None:
            self.messages.append({
                "role" : "user",
                "content" : self.goal
            })

    def add_assistant_message(self,content : list[Any]):
        self.messages.append({
            "role" : "assistant",
            "content" : content
        })

    # 将工具执行结果添加到发送消息中
    def add_tool_result(self,tool_id : str,content : str,is_error : bool = False):
        tool_res = {
            "type" : "tool_result",
            "tool_id" : tool_id,
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
            self.messages.append({"role" : "user","content" : tool_res})

    # 检查状态是否不再是 running
    def is_done(self) -> bool:
        return self.status != "running"

    def mark_success(self):
        self.status = "success"

    def mark_failed(self,reason : str):
        self.status = "failed"
        self.reason = reason
