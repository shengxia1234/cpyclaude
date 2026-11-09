from __future__ import annotations

import time
import json
import sys
import asyncio

from cpy_Claude.core.config import config
from cpy_Claude.core.events.bus import EventBus
from cpy_Claude.core.bus.events import (
    RunStartEvent,
    RunFinishEvent,
    ToolCallFailEvent,
    ToolCallFinishEvent,
    ToolCallStartEvent,
    StepStartEvent,
    StepFinishEvent,
    LLMTokenEvent,
    BaseEvent
)
from cpy_Claude.core.transport.socket_client import SocketClient,IpcError
from cpy_Claude.core.runner import AgentRunner
from cpy_Claude.core.bus.commands import EventSubscribeCommand,AgentRunCommand
from typing import Any,Callable,cast,get_args

type Eptinter = Callable[[dict[str,Any]],Any]

class StdoutPrinter:
    # 订阅事件总线并将运行进度格式化打印到终端
    def __init__(self):
        self._inline = False
        self._run_start : float = 0.0
        self._event_printer : dict[str,Eptinter] = {}

        self._event_printer["run.start"] = self._RUN_START_printer
        self._event_printer["run.finish"] = self._RUN_FINISH_printer
        self._event_printer["tool.call_start"] = self._TOOL_CALL_START_printer
        self._event_printer["tool.call_finish"] = self._TOOL_CALL_FINISH_printer
        self._event_printer["tool.call_fail"] = self._TOOL_CALL_FAIL_printer
        self._event_printer["step.start"] = self._STEP_START_printer
        self._event_printer["step.finish"] = self._STEP_FINISH_printer
        self._event_printer["llm.token"] = self._LLM_TOKEN_printer

    def _ensure_newline(self):
        if self._inline:
            print()
            self._inline = False

    # 根据事件具体类型转发到Printer函数中
    async def handle(self,event : dict[str,Any]):
        destP = event.get("type","")
        printer = self._event_printer.get(destP)
        if printer is not None:
            printer(event)

    ## 以下函数用于处理打印事件

    def _RUN_START_printer(self,event : dict[str,Any]):
        EVENT = RunStartEvent.model_validate(event)
        self._run_start = time.monotonic() 
        print(f"[run]{EVENT.run_id}")

    def _RUN_FINISH_printer(self,event : dict[str,Any]):
        EVENT = RunFinishEvent.model_validate(event)
        self._ensure_newline()
        elapsed = time.monotonic() - self._run_start
        print(f"[run] {EVENT.status}  {EVENT.step} steps  {elapsed:.1f}s")

    def _TOOL_CALL_START_printer(self,event : dict[str,Any]):
        EVENT = ToolCallStartEvent.model_validate(event)
        self._ensure_newline()
        params_str = json.dumps(EVENT.params,ensure_ascii=False)
        print(f"[tool] {EVENT.tool_name} {params_str}")

    def _TOOL_CALL_FINISH_printer(self,event : dict[str,Any]):
        EVENT = ToolCallFinishEvent.model_validate(event)
        print(f"[tool] {EVENT.tool_name} ✓  {EVENT.elapsed_ms}ms")

    def _TOOL_CALL_FAIL_printer(self,event : dict[str,Any]):
        EVENT = ToolCallFailEvent.model_validate(event)
        print(
            f"[tool] {EVENT.tool_name} ✗  {EVENT.error_msg}",
            file=sys.stderr,
        )

    def _STEP_START_printer(self,event : dict[str,Any]):
        EVENT = StepStartEvent.model_validate(event)
        self._ensure_newline()
        print(f"[step {EVENT.step}] planning...")

    def _STEP_FINISH_printer(self,event : dict[str,Any]):
        EVENT = StepFinishEvent.model_validate(event)
        self._ensure_newline()
        print(f"[step {EVENT.step}] done")

    def _LLM_TOKEN_printer(self,event : dict[str,Any]):
        EVENT = LLMTokenEvent.model_validate(event)
        print(EVENT.token, end="", flush=True)
        self._inline = True

# 异步核心：连接 daemon，订阅事件，触发 run，等待 run.finished
async def _run_async(cf : config,goal : str) -> int:
    client = SocketClient(cf.host,cf.port)
    try:
        await client.connect()
    except (ConnectionRefusedError,OSError):
        print(f"The daemon is not running at {cf.host}:{cf.port}")
        return 1
    Printer = StdoutPrinter()
    exit_code = 0
    finished = asyncio.Event()
    async def on_event(event : dict[str,Any]):
        nonlocal exit_code
        type = event.get("type","")
        await Printer.handle(event)
        if type == "run.finish":
            if event.get("status") != "success":
                exit_code = 1
            finished.set()
    client.on_event(on_event)

    loop_task = asyncio.create_task(client.run_event_loop())

    try:
        await client.send_command("event.subscribe",EventSubscribeCommand(
            scope="global",
            topics=[
                "run.*","step.*","tool.*","llm.token","llm.usage"
            ],
            replay_from_run=None
        ).model_dump())
        await client.send_command("agent.run",AgentRunCommand(goal=goal).model_dump())
    except IpcError as e:
        print(f"error : {e}",file=sys.stderr)
        finished.set()
        exit_code = 1

    await finished.wait()

    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass # cancel后返回CancelledError
    await client.close()
    return exit_code

def cmd_run(goal : str,cf : config):
    try:
        exit_code = asyncio.run(_run_async(cf,goal))
    except KeyboardInterrupt:
        sys.exit(130)
    sys.exit(exit_code)
    