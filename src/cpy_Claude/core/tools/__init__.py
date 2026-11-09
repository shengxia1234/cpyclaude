from __future__ import annotations

from cpy_Claude.core.tools.builtin.read_file import ReadFileTool
from cpy_Claude.core.tools.registry import ToolRegistry

TOOLS = ToolRegistry()
TOOLS.register(ReadFileTool())
