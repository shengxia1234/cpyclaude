from __future__ import annotations

from pydantic import BaseModel
from typing import Any,Literal

class TraceRecord(BaseModel):
    ts: str
    direction: Literal[
        "CLIENT->CORE",
        "CORE->CLIENT",
        "CORE",
        "CORE->LLM",
        "LLM->CORE",
    ] # 数据流动方向
    layer: Literal["ipc", "event", "llm"] # 事件发生的层次
    kind: str  # command / response / error / push / event / api_call / api_response,细分
    run_id: str | None = None
    step: int | None = None
    client_id: str | None = None
    data: dict[str, Any]