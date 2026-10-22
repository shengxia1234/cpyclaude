from __future__ import annotations

from cpy_Claude.core.tools.base import BaseTool

class ToolRegistry:
    def __init__(self):
        self.registry : dict[str,BaseTool] = {}

    # 注册工具；同名覆盖
    def register(self,name : str,tool : BaseTool):
        self.registry[name] = tool
        
    # 按名称查找工具，不存在返回 None
    def get(self,name : str):
        return self.registry.get(name)

    # 返回所有工具的 Anthropic 格式 schema 列表
    def tool_schema(self):
        return [
            {
                "name" : tool.name,
                "description" : tool.description,
                "input_schema" : tool.input_schema
            }
            for tool in self.registry.values()
        ]