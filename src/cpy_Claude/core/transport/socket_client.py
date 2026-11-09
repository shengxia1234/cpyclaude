from __future__ import annotations

import asyncio
import uuid
import json

from typing import Callable,Awaitable,Any
from pydantic import BaseModel
from cpy_Claude.core.bus.envelope import JsonRpcRequest


type PushEventHandler = Callable[[dict[str,Any]],Awaitable[Any]]
_MAX_LINE_BYTES = 1 * 1024 * 1024  # 1 MB per frame

class IpcError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


class SocketClient:
    def __init__(self,host : str,port : int):
        self._host = host
        self._port = port
        self._reader : asyncio.StreamReader | None = None
        self._writer : asyncio.StreamWriter | None = None
        self._pending : dict[str,asyncio.Future[dict[str,Any]]] = {} # 依据请求id保存等待结果的协程
        self._event_handler : list[PushEventHandler] = []

    async def connect(self):
        self._reader,self._writer = await asyncio.open_connection(self._host,self._port,limit=_MAX_LINE_BYTES)

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(),timeout=1.0)
            except TimeoutError:
                pass

    # 注册服务器推送事件的回调，可多次调用以添加多个 handler(client->server->client->handler)
    def on_event(self,handler : PushEventHandler):
        self._event_handler.append(handler)

    # 发送 JSON-RPC 命令并等待响应，成功返回 result dict
    async def send_command(self,method : str,params : dict[str,Any]) -> dict[str,Any]:
        if self._writer is None:
            raise RuntimeError("The connection writer is None.")
        req_id = (str)(uuid.uuid4())
        req = JsonRpcRequest(id=req_id,method=method,params=params)
        fut : asyncio.Future[dict[str,Any]] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        self._writer.write(req.model_dump_json().encode() + b"\n")
        await self._writer.drain()
        return await fut
    
    # 持续读取服务器消息，分发 RPC 响应到 pending future 或事件到 event handler
    async def run_event_loop(self):
        if self._reader is None:
            raise RuntimeError("The connection reader is None.")
        try:
            while True:
                try:
                    line = await self._reader.readline()
                except (ConnectionResetError,OSError):
                    break
                if not line:
                    break
                await self._dispatch(line) 
        finally:
            for f in self._pending.values():
                if not f.done():
                    f.cancel()
            self._pending.clear()

    # 解析单行消息并路由到 pending future（RPC 响应）或 event handler（服务器推送）
    async def _dispatch(self,line : bytes):
        try:
            res : dict[str,Any] = json.loads(line)
        except json.JSONDecodeError:
            return RuntimeError("The JsonRpc message can not be decoded.")
        if res.get("jsonrpc") is not None:
            req_id = res["id"]
            fut = self._pending.pop(req_id)
            if not fut.done():
                if res.get("error") is None:
                    fut.set_result(res.get("result",{}))
                else:
                    error : dict[str,Any] = res["error"]
                    fut.set_exception(
                        IpcError(error.get("code",-1),error.get("message","unknown"))
                    )
        elif res.get("kind") == "event":
            for handler in self._event_handler:
                await handler(res["event"])