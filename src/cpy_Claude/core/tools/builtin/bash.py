from __future__ import annotations

import asyncio

from pathlib import Path
from cpy_Claude.core.tools.base import BaseTool, ToolResult

_MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB
_DEFAULT_TIMEOUT = 120

class BashTool(BaseTool):
    name = "bash"
    description = (
        "Execute a shell command and return its output (stdout + stderr combined). "
        "Non-interactive only — commands requiring user input will hang and time out. "
        "Prefer short, focused commands. Output is truncated at 64 KB."
    )
    input_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": f"Maximum seconds to wait (default {_DEFAULT_TIMEOUT}, max 120).",
            },
        },
        "required": ["command"],
    }
    # 在子进程中执行 shell 命令，合并 stdout/stderr，超时或非零退出码时返回错误
    async def invoke(self, params: dict[str, object]) -> ToolResult:
        command = params.get("command")
        if command is None:
            return ToolResult(f"The BashTool received an invalid value '{command}' for the 'command' argument",True,"runtime_error")
        command = str(command)
        timeout = min(int(str(params.get("timeout",_DEFAULT_TIMEOUT))),_DEFAULT_TIMEOUT)
        if timeout < 0:
            return ToolResult(f"The BashTool received an invalid value '{timeout}' for the 'timeout' argument",True,"runtime_error")
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            try:
                stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(
                    content=f"[timeout after {timeout}s]",
                    is_error=True,
                    error_type="timeout",
                )
        except Exception as exc:
            return ToolResult(content=str(exc), is_error=True, error_type="runtime_error")
        # 截断输出
        truncated = len(stdout_bytes) > _MAX_OUTPUT_BYTES
        if truncated:
            output = stdout_bytes[:_MAX_OUTPUT_BYTES].decode(errors="ignore") + "\n[truncated]"
        else:
            output = stdout_bytes.decode(errors="ignore")

        return_code = proc.returncode or 0
        if return_code != 0:
            return ToolResult(
                content=f"[exit {return_code}]\n{output}",
                is_error=True,
                error_type="runtime_error",
            )
        return ToolResult(content=output or "[no output]")