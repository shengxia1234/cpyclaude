from __future__ import annotations

import asyncio
from pathlib import Path

from cpy_Claude.core.trace.record import TraceRecord

class TraceWriter:
    # 保存路径，建立无界记录队列和空消费者任务引用
    def __init__(self,path : Path):
        self._path = path
        self._queue : asyncio.Queue[TraceRecord] = asyncio.Queue()
        self._task : asyncio.Task[None] | None = None # 将协程包装成任务

    # 创建父目录并启动 _drain 消费协程；不在这里同步写记录。
    async def start(self):
        self._path.parent.mkdir(parents=True,exist_ok=True)
        self._task = asyncio.create_task(self._drain())

    # 等待所有已入队记录 task_done，再取消并等待消费者结束。task_done会让queue计数-1
    async def stop(self):
        await self._queue.join()
        if self._task is not None:
            self._task.cancel()
            try:   
                await self._task
            except asyncio.CancelledError:
                pass

    # 以 put_nowait 同步入队，不执行 await 或直接文件写入。
    def emit(self,record : TraceRecord):
        self._queue.put_nowait(record)

    # 串行消费并追加 NDJSON，每条 flush，finally 标记 task_done；文件 I/O 仍是同步调用。
    async def _drain(self):
        with self._path.open("a") as f:
            while True:
                record = await self._queue.get()
                try:
                    f.write(record.model_dump_json() + "\n")
                    f.flush()
                finally:
                    self._queue.task_done()
