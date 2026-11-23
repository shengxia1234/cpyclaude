from __future__ import annotations

from cpy_Claude.core.tools.base import BaseTool, ToolResult
from cpy_Claude.core.task.manager import TaskManager

class TaskGetTool(BaseTool):
    name = "task_get"
    description = "Get full details of a task by its integer ID. Returns the task as JSON."
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "ID of the task to retrieve.",
            },
        },
        "required": ["task_id"],
    }

    # 保存注入的当前运行 TaskManager，保证任务工具访问同一任务目录
    def __init__(self,task_manager : TaskManager):
        self.manager = task_manager

    # 转换 task_id，获取任务并返回 JSON；遵循 ToolResult 接口
    async def invoke(self,params : dict[str,object]) -> ToolResult:
        task_id = params.get("task_id")
        if task_id is None:
            return ToolResult(f"The TaskGetTool received an invalid value '{task_id}' for the 'task_id' argument",True,"runtime_error")
        task_id = int(str(task_id))
        try:
            task = self.manager.get(task_id)
            return ToolResult(task.model_dump_json())
        except ValueError as exc:
            return ToolResult(str(exc),True,"runtime_error")

    