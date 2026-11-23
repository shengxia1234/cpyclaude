from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import signal
import psutil

from pathlib import Path
from cpy_Claude.core.config import config
from cpy_Claude.core.transport.socket_client import SocketClient
from cpy_Claude.core.bus.commands import ShutDownServerCommand

_PID_FILE = Path.home() / ".cpyClaude" / "cpyClaude.pid"

# 尝试连接 daemon，成功则正常返回，失败则抛出 ConnectionRefusedError/OSError
async def _ping_check(cf : config):
    _,writer = await asyncio.open_connection(cf.host,cf.port)
    writer.close()
    await writer.wait_closed()

# 读取 PID 文件并确认进程存活，进程已消失则删除文件并返回 None
def _running_pid() -> int | None:
    if not _PID_FILE.exists():
        return -1
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
        print("The daemon is not running")

async def _core_status(cf : config) -> bool:
    try:
        task = asyncio.create_task(_ping_check(cf))
        await task
    except (ConnectionRefusedError,OSError):
        return False
    return True

# 在后台启动 daemon，若已在运行则提示并退出
async def cmd_core_start(cf : config):
    try:
        task = asyncio.create_task(_ping_check(cf))
        await task
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

async def cmd_core_stop(cf : config):
    pid = _running_pid() # 返回-1时可能是pid文件被删或daemon没有运行
    if pid and pid >= 0:
        os.kill(pid,signal.SIGTERM)
        _PID_FILE.unlink(missing_ok=True)
        print("The daemon is being stopped")
    elif pid and pid < 0:
        res = await cmd_core_shutdown(cf)
        if res == 0:
            print("close the daemon using rpc")
    else:
        print("The daemon is not running now")

async def cmd_core_shutdown(cf : config) -> int:
    client = SocketClient(cf.host,cf.port)
    try:
        await client.connect()
    except (ConnectionRefusedError,OSError):
        print(f"The daemon is not running at {cf.host}:{cf.port}")
        return 1
    await client.send_shutdown_command(method="core.shutdown",params=ShutDownServerCommand().model_dump())
    await client.close()
    return 0

async def cmd_core_restart(cf : config):
    status = await _core_status(cf)
    if status is True:
        pid = _running_pid()
        if pid and pid >= 0:
            try:
                proc = psutil.Process(pid)
                await cmd_core_stop(cf)
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                print("The daemon has already been stopped")
            except psutil.TimeoutExpired:
                print("Wait timed out, the daemon has not exited")
                print("Please stop and start the daemon manually")
                return
            await cmd_core_restart(cf)
        elif pid and pid < 0:
            await cmd_core_stop(cf)
            try_num = 0
            while(await _core_status(cf) and try_num < 5):
                try_num += 1
                await asyncio.sleep(1)
            if not await _core_status(cf):
                await cmd_core_start(cf)
            else:
                print("The daemon is still running now,please wait a monent")
    else:
        await cmd_core_start(cf)
