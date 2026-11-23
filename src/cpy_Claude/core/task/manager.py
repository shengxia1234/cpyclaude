from __future__ import annotations

import datetime
import re
import json

from pydantic import ValidationError
from pathlib import Path
from typing import Any,Literal
from cpy_Claude.core.task.model import Task

tz = datetime.timezone(datetime.timedelta(hours=8))
def _now() -> str:
    return datetime.datetime.now(tz).isoformat()

class TaskManager:
    # 初始化：确保目录存在，扫描现有文件确定下一个 ID
    def __init__(self,task_dir : Path):
        self._dir = task_dir
        self._dir.mkdir(parents=True,exist_ok=True)
        self.next_id = self._max_id() + 1

    # 获取文件最大ID
    def _max_id(self):
        max_id = 0
        for path in self._dir.glob("task_*.json"):
            match = re.fullmatch(r"task_(\d+)\.json", path.name)
            if match:
                max_id = max(max_id, int(match.group(1)))
        return max_id

    # 读取指定 ID 的任务文件
    def _load(self,task_id : int) -> Task:
        task_file = self._dir / f"task_{task_id}.json"
        if not task_file.exists():
            raise ValueError(f"The task file {str(task_file)} not exists")
        tmp : dict[str,Any] = json.loads(task_file.read_text())
        try:
            return Task.model_validate(tmp)
        except ValidationError:
            raise SystemError(f"The task file info can not be loaded in Task class:{tmp}")
    
    # 将任务写入对应 JSON 文件
    def _save(self,task : Task):
        task_file = self._dir / f"task_{task.id}.json"
        task_file.write_text(json.dumps(task.model_dump(),indent=2,ensure_ascii=False))

    # 创建新任务，写入 JSON 文件，返回 Task
    def create(
        self,
        subject : str,
        description: str,
        blocked_by: list[int] | None = None
    ) -> Task:
        task_file = self._dir / f"task_{self.next_id}.json"
        for blocked_id in blocked_by or []:
            blocked_file = self._dir / f"task_{blocked_id}.json"
            if not blocked_file.exists():
                raise ValueError(f"The blocked file {str(blocked_file)} not exists")
        task : Task = Task(
            id=self.next_id,
            subject=subject,
            description=description,
            status="pending",
            blocked_by=blocked_by if blocked_by else [],
            created_at=_now(),
            updated_at=_now()
        )
        task_file.write_text(json.dumps(task.model_dump(),indent=2,ensure_ascii=False)) # 自动创建文件
        self.next_id += 1
        return task

    # 读取指定 ID 的任务
    def get(self,task_id : int) -> Task:
        return self._load(task_id)

    # 更新任务状态或依赖列表；status="completed" 时自动清理其他任务的 blocked_by
    def update(
        self,
        task_id : int,
        status : Literal["pending","in_progress","completed"] | None = None,
        add_blocked_by : list[int] | None = None,
        remove_blocked_by : list[int] | None = None
    ) -> Task:
        task = self._load(task_id)
        if status == "completed":
            self._clear_dependency(task_id)
        if status is not None:
            if status not in ["pending","in_progress","completed"]:
                raise ValueError(f"invalid status: {status!r}")
            task.status = status
        if add_blocked_by:
            for add_id in add_blocked_by:
                if add_id in task.blocked_by:
                    continue
                task.blocked_by.append(add_id)
        if remove_blocked_by:
            task.blocked_by = [rid for rid in task.blocked_by if rid not in remove_blocked_by]
        task.updated_at = _now()
        self._save(task)
        return task
                    

    # 返回所有任务，按 ID 升序排列
    def list_all(self) -> list[Task]:
        task_list : list[Task] = []
        for file in sorted(self._dir.glob("task_*.json"),key=lambda p : int(p.stem.split("_")[1])):
            try:
                task = Task.model_validate_json(file.read_text())
                task_list.append(task)
            except (ValueError,KeyError):
                pass
        return task_list
            
    # 将 completed_id 从所有其他任务的 blocked_by 列表中移除
    def _clear_dependency(self,completed_id : int):
        for file in self._dir.glob("task_*.json"):
            task = Task.model_validate_json(file.read_text())
            if completed_id in task.blocked_by:
                task.blocked_by = [id for id in task.blocked_by if id != completed_id]
                task.updated_at = _now()
                file.write_text(json.dumps(task.model_dump(),indent=2,ensure_ascii=False))
                

    # 格式化任务列表摘要，供 task_list 工具返回给 Agent
    def format_list(self):
        tasks = self.list_all()
        if not tasks:
            return "No tasks."
        marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
        lines = []
        for t in tasks:
            blocked = f" (blocked by: {t.blocked_by})" if t.blocked_by else ""
            lines.append(f"{marker.get(t.status, '[?]')} #{t.id}: {t.subject}{blocked}")
        return "\n".join(lines)