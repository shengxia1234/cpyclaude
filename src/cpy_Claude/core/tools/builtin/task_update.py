from __future__ import annotations

from cpy_Claude.core.tools.base import BaseTool, ToolResult
from cpy_Claude.core.task.manager import TaskManager

class TaskUpdateTool(BaseTool):
    name = "task_update"
    description = (
        "Update a task's status or dependency list. "
        "Set status to 'in_progress' when starting work on a task, "
        "'completed' when finished (automatically clears it from other tasks' blocked_by). "
        "Returns the updated task as JSON."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "integer",
                "description": "ID of the task to update.",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"],
                "description": "New status for the task.",
            },
            "add_blocked_by": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Task IDs to add to blocked_by.",
            },
            "remove_blocked_by": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Task IDs to remove from blocked_by.",
            },
        },
        "required": ["task_id"],
    }

    # 保存注入的当前运行 TaskManager，保证任务工具访问同一任务目录
    def __init__(self,task_manager : TaskManager):
        self.manager = task_manager

    # 转换 task_id 和依赖数组，更新状态/依赖并返回 JSON；遵循 ToolResult 接口。
    async def invoke(self,params : dict[str,object]) -> ToolResult:
        task_id = params.get("task_id")
        if task_id is None:
            return ToolResult(f"The TaskUpdateTool received an invalid value '{task_id}' for the 'task_id' argument",True,"runtime_error")
        task_id = int(str(task_id))
        status = params.get("status")
        status = str(status) if status is not None else None
        raw_add_blocked_by : list[object] = list(params.get("add_blocked_by") or []) # type: ignore[call-overload] (忽略静态类型错误:不是所有object都可迭代)
        add_blocked_by = [int(str(x)) for x in raw_add_blocked_by]
        raw_remove_blocked_by : list[object] = list(params.get("remove_blocked_by") or []) # type: ignore[call-overload]
        remove_blocked_by = [int(str(x)) for x in raw_remove_blocked_by]
        try:
            task = self.manager.update(task_id,status,add_blocked_by,remove_blocked_by) # type: ignore[arg-type]
            return ToolResult(task.model_dump_json())
        except ValueError as exc:
            return ToolResult(str(exc),True,"runtime_error")