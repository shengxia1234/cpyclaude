from __future__ import annotations

from pathlib import Path
from cpy_Claude.core.tools.base import BaseTool, ToolResult

_MAX_DEPTH = 4
_MAX_ENTRIES = 200

class ListDirTool(BaseTool):
    name = "list_dir"
    description = (
        "List the contents of a directory as a tree. "
        "Path must be relative to the current working directory. "
        "Hidden entries (starting with .) are included. "
        f"Maximum depth is {_MAX_DEPTH}, maximum total entries is {_MAX_ENTRIES}."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the directory (default '.').",
            },
            "max_depth": {
                "type": "integer",
                "description": f"How many levels deep to recurse (default 2, max {_MAX_DEPTH}).",
            },
        },
        "required": [],
    }

    # 校验目录路径，设置深度/数量限制，调用内部遍历函数并返回目录树文本
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        path_str = str(params.get("path","."))
        max_depth_argu = int(str(params.get("max_depth","2")))
        max_depth = min(max_depth_argu,_MAX_DEPTH)
        rootpath = Path(path_str)
        # 不能访问上一级目录
        if ".." in rootpath.parts:
            # 错误会被上一层的调用方捕获，与返回带有错误信息的ToolResult效果相同
            raise PermissionError(f"path traversal is not allowed:{path_str}")
        # 禁止访问绝对路径
        if rootpath.is_absolute():
            raise PermissionError(f"Access to absolute paths is prohibited:{path_str}")
        if not rootpath.exists():
            raise FileNotFoundError(f"no such file:{rootpath}")
        if not rootpath.is_dir():
            raise NotADirectoryError(f"not a directory:{rootpath}")
        
        count = 0
        def _walk(root: Path, max_depth: int, max_entries: int) -> list[str]:
            nonlocal count
            lines = []
            def visit(path: Path, depth: int, prefix: str):
                nonlocal count
                if depth > max_depth or count >= max_entries:
                    return
                try:
                    entries = sorted(
                        path.iterdir(),
                        key=lambda p: (not p.is_dir(), p.name.lower())
                    )
                except OSError:
                    return
                for i, entry in enumerate(entries):
                    if count >= max_entries:
                        lines.append(">maxentries:[truncated]")
                        break
                    is_last = (i == len(entries) - 1)
                    is_dir = entry.is_dir()
                    branch = "└── " if is_last else "├── "
                    lines.append(
                        prefix + branch + entry.name + ("/" if is_dir else "")
                    )
                    count += 1
                    if is_dir and not entry.is_symlink() and depth < max_depth:
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        visit(entry, depth + 1, next_prefix)
            visit(root, 1, "")
            return lines
        res : list[str] = _walk(rootpath,max_depth,_MAX_ENTRIES)
        return ToolResult("\n".join(res))
