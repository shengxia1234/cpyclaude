from __future__ import annotations

from pathlib import Path
from cpy_Claude.core.tools.base import BaseTool, ToolResult

_MAX_BYTES = 1024 * 1024

class WriteFileTool(BaseTool):
    name = "write_file"
    description = (
        "Write text content to a file, creating it (and any parent directories) if it "
        "does not exist, or overwriting it if it does. "
        "Path must be relative to the current working directory. "
        "Content size is limited to 1 MB."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file (relative to current working directory).",
            },
            "content": {
                "type": "string",
                "description": "Text content to write.",
            },
        },
        "required": ["path", "content"],
    }

    # 写入文件内容；超 1MB 拒绝；禁止 .. 路径遍历；自动创建父目录
    async def invoke(self,params : dict[str,object]) -> ToolResult:
        path_str = params.get("path")
        if path_str is None:
            return ToolResult(f"The WriteFileTool received an invalid value '{path_str}' for the 'path_str' argument",True,"runtime_error")
        path = Path(str(path_str))
        # 不能访问上一级目录
        if ".." in path.parts:
            raise PermissionError(f"path traversal is not allowed:{path_str}")
        # 禁止访问绝对路径
        if path.is_absolute():
            raise PermissionError(f"Access to absolute paths is prohibited:{path_str}")
        content = params.get("content")
        if content is None:
            return ToolResult(f"The WriteFileTool received an invalid value '{content}' for the 'content' argument",True,"runtime_error")
        content = str(content)
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_BYTES:
            return ToolResult(
                content=f"content too large: {len(encoded)} bytes (limit 1 MB)",
                is_error=True,
                error_type="runtime_error",
            )
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content,"utf-8")
        return ToolResult(content=f"wrote {len(encoded)} bytes to {path_str}")      