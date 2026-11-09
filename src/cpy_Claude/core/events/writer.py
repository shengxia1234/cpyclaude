# Agent事件落盘
from __future__ import annotations

import logging

from pydantic import BaseModel
from pathlib import Path
from typing import IO
from cpy_Claude.core.events.bus import EventBus


class EventWriter:
    def __init__(self,path : Path):
        self._path = path
        self._file : IO[str] | None = None
        self._pending_events : int = 0

    async def __aenter__(self) -> EventWriter:
        # 递归创建目录
        self._path.parent.mkdir(parents=True,exist_ok=True)
        # append模式打开文件
        self._file = open(self._path,"a",encoding="utf-8")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._file is not None:
            self._file.close()
            self._file = None

    async def handle(self,event : BaseModel):
        if self._file is not None:
            try:
                self._file.write(event.model_dump_json() + "\n")
                if self._pending_events >= 100:
                    self._file.flush()
                    self._pending_events = 0
            except (OSError,ValueError) as e:
                logging.error("Event Write error:%s",e)

    def subscribe(self,bus : EventBus):
        bus.subscribe(self.handle)