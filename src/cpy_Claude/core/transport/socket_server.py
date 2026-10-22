from __future__ import annotations

import asyncio
import sys
import logging
import json

from pydantic import BaseModel,ValidationError
from collections.abc import Awaitable, Callable
from typing import Any
from cpy_Claude.core.bus.envelope import JsonRpcRequest,JsonRpcSuccess
from cpy_Claude.core.bus.envelope import (
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    make_error
)

# 定义可调用对象,传入参数为 dict[str,Any],且函数为可使用await的对象，返回值为Any
type CommandHandler = Callable[[dict[str, Any]], Awaitable[Any]]
_MAX_LINE_BYTES = 1 * 1024 * 1024  # 1 MB per frame
logger = logging.getLogger(__name__)


class SocketServer:
    def __init__(self,host : str,port : int) -> None:
        self._host = host
        self._port = port
        self._handler : dict[str,CommandHandler] = {}
        self._server : asyncio.AbstractServer | None = None

    # 注册一个方法名对应的命令处理函数
    def register(self,method : str,handler : CommandHandler) -> None:
        self._handler[method] = handler

    # 启动 TCP 服务器；若端口已被占用则退出进程
    async def start(self) -> str:
        try:
            _r,w = await asyncio.open_connection(self._host,self._port)
            w.close()
            await w.wait_closed()
            # 如果连接成功，说明目标ip:port有服务在监听,就退出程序
            raise SystemExit(f"core has already run at {self._host}:{self._port}")
        except (OSError,ConnectionRefusedError):
            pass

        # 创建一个 TCP 监听 Socket，等待客户端连接，并在每个客户端连接建立后调用指定的回调函数处理通信
        self._server = await asyncio.start_server(
            client_connected_cb=self._handle_connection,
            host=self._host,
            port=self._port,
            limit=_MAX_LINE_BYTES,
        )
        return f"{self._host}:{self._port}"

    # 关闭服务器，最多等待 2 秒
    async def stop(self):
        if self._server is None:
            return
        self._server.close()
        try:
            await asyncio.wait_for(self._server.wait_closed(),timeout=2.0)
        except (TimeoutError):
            print("server closes timeout:2.0s")
            sys.exit(1)

    # 处理单个客户端连接，完成后关闭写流
    async def _handle_connection(
        self,
        reader : asyncio.StreamReader,
        writer : asyncio.StreamWriter,
    ):
        peer = writer.get_extra_info("peername","unknown")
        logger.debug("client connect:%s",peer)
        try:
            await self._read_loop(reader=reader,writer=writer)
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(),timeout=1.0)
            except TimeoutError:
                pass
        logger.debug("client disconnect:%s",peer)

    # 持续读取换行分隔的 JSON 行并逐行分发处理
    async def _read_loop(
        self,
        reader : asyncio.StreamReader,
        writer : asyncio.StreamWriter,
    ) -> None:
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
            except asyncio.LimitOverrunError:
                await self._send(writer,make_error(None,INVALID_REQUEST,"Request message too large."))
            await self._handle_line(line,writer)

    # 解析单行 JSON-RPC 请求并调用对应 handler，将结果或错误写回客户端
    async def _handle_line(self,line : bytes,writer : asyncio.StreamWriter) -> None:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            await self._send(writer,make_error(None,PARSE_ERROR,f"Parse error: {e}"))
            return

        try:
            req = JsonRpcRequest.model_validate(raw)
        except ValidationError as e:
            await self._send(writer,make_error(None,INVALID_REQUEST,f"Invalid request: {e}"))
            return

        # 使用[]获取，在没有这个key时会返回异常
        # if self._handler[req.method] is None:
        #     self._send(writer,make_error(req.id,METHOD_NOT_FOUND,f"method {req.method} not found"))

        handler = self._handler.get(req.method)
        if handler is None:
            await self._send(writer,make_error(req.id,METHOD_NOT_FOUND,f"method '{req.method}' not found"))
            return

        res = await handler(req.params)
        await self._send(writer,JsonRpcSuccess(id=req.id,result=res))

    # 将 pydantic 消息序列化为 JSON 行并写入流，随后刷新缓冲区
    async def _send(
        self,
        writer : asyncio.StreamWriter,
        msg : BaseModel
    ):
        writer.write(msg.model_dump_json().encode() + b"\n")
        await writer.drain()
        