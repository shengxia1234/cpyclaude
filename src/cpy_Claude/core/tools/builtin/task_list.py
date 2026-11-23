from __future__ import annotations

from cpy_Claude.core.tools.base import BaseTool, ToolResult
from cpy_Claude.core.task.manager import TaskManager

class TaskListTool(BaseTool):
    name = "task_list"
    description = (
        "List all tasks with their current status and blocking dependencies. "
        "Use this to check what work remains and what can be started next."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    # 保存注入的当前运行 TaskManager，保证任务工具访问同一任务目录
    def __init__(self,task_manager : TaskManager):
        self.manager = task_manager

    # 返回管理器格式化后的任务列表；遵循 ToolResult 接口
    async def invoke(self,params : dict[str,object]) -> ToolResult:
        return ToolResult(self.manager.format_list())