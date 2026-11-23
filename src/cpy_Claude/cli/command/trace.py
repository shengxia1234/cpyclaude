from __future__ import annotations

import sys
import time

from typing import Literal
from cpy_Claude.core.config import config
from cpy_Claude.core.trace.record import TraceRecord
from pathlib import Path

_COLORS = {
    "CLIENT->CORE": "\033[36m", #青色
    "CORE->CLIENT": "\033[33m", # 黄色
    "CORE":             "\033[32m", # 绿色
    "CORE->LLM":   "\033[35m", # 紫色
    "LLM->CORE":   "\033[34m", #蓝色
}
_RESET = "\033[0m" # 重置
_BOLD = "\033[1m" # 粗体

# 读取历史 trace；传递过滤条件；可进入轮询跟随模式。文件不存在时打印错误并退出。
def cmd_trace(
    cf : config,
    run_id : str | None = None,
    layer : Literal["ipc", "event", "llm"] | None = None,
    direction : Literal["CORE","CORE->LLM","LLM->CORE","CORE->CLIENT","CLIENT->CORE"] | None = None,
    raw : bool = False,
    follow : bool = False
):
    trace_path = Path(cf.trace.file).expanduser()
    if not trace_path.exists():
        print("The trace file is not exist or the trace file path is wrong")
        sys.exit(1)
    with trace_path.open("+r") as file:
        for line in file:
            _process_line(line.strip(),run_id,layer,direction,raw)
        if follow:
            while True:
                try:
                    line = file.readline()
                    if line:
                        _process_line(line.strip(),run_id,layer,direction,raw)
                    else:
                        time.sleep(0.05)
                except KeyboardInterrupt:
                    print("\nExit the trace terminal")
                    sys.exit(0)

# 跳过空行/无效 JSON 或模型，按 run_id/layer/direction 精确过滤，再输出原始行或摘要。
def _process_line(
    line : str,
    run_id : str | None = None,
    layer : Literal["ipc", "event", "llm"] | None = None,
    direction : Literal["CORE","CORE->LLM","LLM->CORE","CORE->CLIENT","CLIENT->CORE"] | None = None,
    raw : bool = False
):
    try:
        record = TraceRecord.model_validate_json(line)
    except Exception:
        return
    
    if run_id is not None and record.run_id != run_id:
        return
    if layer is not None and record.layer != layer:
        return
    if direction is not None and record.direction != direction:
        return
    
    if raw:
        print(record)
    else:
        _print_record(record)

# 格式化时间和流向颜色，附加 run/step 与摘要，不打印完整大 payload。
def _print_record(record : TraceRecord):
    color = _COLORS.get(record.direction, "")
    ts = record.ts[11:23] if len(record.ts) >= 23 else record.ts

    direction_str = f"{color}{_BOLD}{record.direction:<14}{_RESET}"
    kind_str = f"{record.kind:<13}"

    parts: list[str] = []
    if record.run_id:
        parts.append(f"run={record.run_id[:8]}")
    if record.step is not None:
        parts.append(f"step={record.step}")
    parts.append(_summarize(record))

    print(f"{ts}  {direction_str}  {kind_str}  {'  '.join(parts)}")

# 按 kind 提取请求方法、响应、错误、事件或 LLM 用量/延迟等摘要。
def _summarize(record : TraceRecord):
    data = record.data
    kind = record.kind

    if kind == "command":
        params = data.get("params", {})
        goal = str(params.get("goal", ""))
        suffix = f'  goal="{goal[:50]}"' if goal else ""
        return f"method={data.get('method')}{suffix}"

    if kind == "response":
        result = data.get("result", {})
        if isinstance(result, dict) and "run_id" in result:
            return f"run_id={result['run_id'][:8]}"
        return str(result)[:60]

    if kind == "error":
        err = data.get("error", {})
        return f"code={err.get('code')}  {err.get('message', '')}"

    if kind == "push":
        return f"event={data.get('event_type')}  sub={data.get('sub_id')}"

    if kind == "event":
        return f"type={data.get('type')}"

    if kind == "api_call":
        msgs = data.get("messages")
        count = len(msgs) if isinstance(msgs, list) else data.get("message_count", "?")
        tools = data.get("tool_schemas")
        tc = len(tools) if isinstance(tools, list) else data.get("tool_count", "?")
        return f"msgs={count}  tools={tc}"

    if kind == "api_response":
        usage = data.get("usage", {})
        return (
            f"stop={data.get('stop_reason')}  "
            f"latency={data.get('latency_ms')}ms  "
            f"out_tokens={usage.get('output_tokens', '?')}"
        )

    return str(data)[:60]
