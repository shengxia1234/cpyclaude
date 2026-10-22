from __future__ import annotations

from pathlib import Path
from cpy_Claude.core.tools.base import BaseTool, ToolResult

_MAX_BYTES = 512 * 1024

class ReadFileTool(BaseTool):
    name = "read_file"
    description = (
        "Read the text content of a file. "
        "Path must be relative to the current working directory. "
        "Files larger than 512 KB are truncated."
    )
    # Anthropic
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file (relative to current working directory).",
            }
        },
        "required": ["path"],
    }

    async def invoke(self, params: dict[str, object]) -> ToolResult:
        path_str = str(params["path"])
        path = Path(path_str)
        # 不能访问上一级目录
        if ".." in path.parts:
            raise PermissionError(f"path traversal is not allowed:{path_str}")

        # 禁止访问绝对路径
        if path.is_absolute():
            raise PermissionError(f"Access to absolute paths is prohibited:{path_str}")

        raw = path.read_bytes()
        is_truncated = len(raw) > _MAX_BYTES
        text = raw[:_MAX_BYTES].decode("utf-8", errors="replace")
        if is_truncated:
            text += "\n[truncated]"

        return ToolResult(content=text)

        

        
