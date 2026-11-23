from __future__ import annotations

from pydantic import BaseModel
from typing import Any,Literal

class Task(BaseModel):
    id: int
    subject: str # 主题
    description: str # 任务描述
    status: Literal["pending","in_progress","completed"]
    blocked_by: list[int] # 依赖的任务id
    created_at: str
    updated_at: str