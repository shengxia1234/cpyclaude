from __future__ import annotations

from cpy_Claude.core.tools.base import BaseTool, ToolResult
from cpy_Claude.core.task.manager import TaskManager

class TaskCreateTool(BaseTool):
    name : str = "task_create"
    description : str = (
        "Create a new task to track a unit of work. "
        "When dealing with complex tasks (such as tasks that require multiple steps to complete), please use this tool."
        "Use this to break down a complex goal into smaller, trackable steps. "
        "Returns the created task as JSON."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Short title for the task.",
            },
            "description": {
                "type": "string",
                "description": "Optional longer description of what needs to be done.",
            },
            "blocked_by": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "IDs of tasks that must be completed before this one.",
            },
        },
        "required": ["subject"],
    }

    # 持有 TaskManager 实例，供 invoke 调用
    def __init__(self,task_manager : TaskManager):
        self.manager = task_manager

    # 创建任务并返回 JSON 字符串
    async def invoke(self,params : dict[str,object]) -> ToolResult:
        subject = params.get("subject")
        if subject is None:
            return ToolResult(f"The TaskCreateTool received an invalid value '{subject}' for the 'subject' argument",True,"runtime_error")
        subject = str(subject)
        description = str(params.get("description",""))
        raw_blocked: list[object] = list(params.get("blocked_by") or [])  # type: ignore[call-overload]
        blocked_by = [int(str(x)) for x in raw_blocked]
        try:
            task = self.manager.create(subject,description,blocked_by)
            return ToolResult(task.model_dump_json())
        except ValueError as exc:
            return ToolResult(str(exc),True,"runtime_error")