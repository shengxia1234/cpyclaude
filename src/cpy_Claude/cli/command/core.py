from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import signal

from pathlib import Path
from cpy_Claude.core.config import config

_PID_FILE = Path.home() / ".cpyClaude" / "cpyClaude.pid"

# 尝试连接 daemon，成功则正常返回，失败则抛出 ConnectionRefusedError/OSError
async def _ping_check(cf : config):
    _,writer = await asyncio.open_connection(cf.host,cf.port)
    writer.close()
    await writer.wait_closed()

# 读取 PID 文件并确认进程存活，进程已消失则删除文件并返回 None
def _running_pid() -> int | None:
    if not _PID_FILE.exists():
        return
    try:
        pid = int(_PID_FILE.read_text().strip())
        # 参数0表示发送信号探测进程是否存活，存活正常返回，否则返回ProcessLookupError，无权限返回PermissionError
        os.kill(pid,0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        _PID_FILE.unlink(missing_ok=True)
        return

# 打印 daemon 当前状态（running / not running）
def cmd_core_status(cf : config):
    try:
        asyncio.run(_ping_check(cf))
        print(f"The daemon is running at {cf.host}:{cf.port}")
    except (ConnectionRefusedError,OSError):
        print("The daemon is not running ")

# 在后台启动 daemon，若已在运行则提示并退出
def cmd_core_start(cf : config):
    try:
        asyncio.run(_ping_check(cf))
        print(f"The daemon is running at {cf.host}:{cf.port}")
        return
    except (ConnectionRefusedError,OSError):
        pass

    # 在相同python解释器路径下以模块的方式启动子进程
    proc = subprocess.Popen(
        [sys.executable,"-m","cpy_Claude.core"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    _PID_FILE.parent.mkdir(parents=True,exist_ok=True)
    # 不存在时自动创建文件
    _PID_FILE.write_text(str(proc.pid))
    print(f"The daemon's started pid:{proc.pid},running at {cf.host}:{cf.port}")

def cmd_core_stop():
    pid = _running_pid()
    if pid is not None:
        os.kill(pid,signal.SIGTERM)
        _PID_FILE.unlink(missing_ok=True)
    print("The daemon has already been stopped")
