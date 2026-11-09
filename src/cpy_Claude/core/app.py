import time
import asyncio
import logging
import signal
import cpy_Claude
import datetime
import fnmatch
import json

from cpy_Claude.core.transport.socket_server import SocketServer
from cpy_Claude.core.bus.commands import PongResult,AgentRunCommand,AgentRunResult,EventSubscribeCommand,EventSubscribeResult
from cpy_Claude.core.config import get_config
from cpy_Claude.core.logging_setup import setup_logging
from cpy_Claude.core.events.bus import EventBus
from cpy_Claude.core.transport.ipc_broadcaster import IpcEventBoardCaster
from cpy_Claude.core.runner import AgentRunner
from cpy_Claude.core.runs import new_run_id,events_file
from cpy_Claude.core.transport.socket_server import get_writer_var
from cpy_Claude.core.bus.envelope import EventPushEnvelope
from typing import Any

logger = logging.getLogger(__name__)

class coreApp:
    def __init__(self) -> None:
        self._start_time = time.monotonic()
        self._bus = EventBus()
        self._boardcaster = IpcEventBoardCaster()
        self._bus.subscribe(self._boardcaster.handle)
        self._config = get_config()
        self._current_run_task : asyncio.Task[None] | None = None

    async def _ping_handler(self,params : dict[str,Any]):
        client = params.get("client", "unknown")
        logger.debug("ping from %s", client)
        tz = datetime.timezone(datetime.timedelta(hours=8))
        return PongResult(
            server_version=cpy_Claude.__version__,
            uptime_ms=int((time.monotonic() - self._start_time) * 1000),
            received_at=datetime.datetime.now(tz).isoformat(),
        )

    # 如果上一次任务还在运行，则拒绝启动新任务
    async def _agent_run_handler(self,params : dict[str,Any]):
        agent_run_command = AgentRunCommand.model_validate(params)
        if self._current_run_task is not None and not self._current_run_task.done():
            raise RuntimeError("The current task is running.")
        run_id = new_run_id()
        runner = AgentRunner(self._config,extra_handlers=[],bus=self._bus)
        goal = agent_run_command.goal
        self._current_run_task = asyncio.create_task(
            runner.run(goal,run_id)
        )
        return AgentRunResult(run_id=run_id)

    async def _event_subscribe_handler(self,params : dict[str,Any]):
        event_subscribe_command = EventSubscribeCommand.model_validate(params)
        writer : asyncio.StreamWriter = get_writer_var()
        replayed_count = 0
        if event_subscribe_command.replay_from_run is not None:
            replayed_count = await self._replay_events(event_subscribe_command.replay_from_run,writer,event_subscribe_command.topics)
        sub_id = self._boardcaster.subscribe(writer=writer,topics=event_subscribe_command.topics,scope=event_subscribe_command.scope)
        return EventSubscribeResult(subscription_id=sub_id,replayed_count=replayed_count)

    # 不使用boardcaster发送是为了防止所有scope为global的client收到回放
    async def _replay_events(self,run_id : str,writer : asyncio.StreamWriter,topics : list[str]) -> int:
        path = events_file(run_id)
        if not path.exists():
            return 0
        count = 0

        for line in path.read_text().splitlines():
            if not line:
                continue
            raw = json.loads(line)
            event_type : str = raw.get("type","")
            if not any(fnmatch.fnmatch(event_type,p) for p in topics):
                continue
            e = EventPushEnvelope(event=raw)
            writer.write(e.model_dump_json().encode() + b"\n")
            count += 1

        if count:
            # 防止服务器发送缓冲区填满
            await writer.drain()
        return count


    async def run(self) -> None:
        self._start_time = time.monotonic()

        setup_logging(self._config)

        server = SocketServer(self._config.host,self._config.port,self._boardcaster)
        server.register("core.ping",self._ping_handler)
        server.register("agent.run",self._agent_run_handler)
        server.register("event.subscribe",self._event_subscribe_handler)

        #启动服务器
        host_port = await server.start()
        logger.info("cpy_Claude Server is now running on %s:%d",self._config.host,self._config.port)

        #设置信号处理,当收到信号时，wait()会返回
        loop = asyncio.get_event_loop()
        shut_down = asyncio.Event()
        loop.add_signal_handler(signal.SIGINT,shut_down.set)
        loop.add_signal_handler(signal.SIGTERM,shut_down.set)

        await shut_down.wait()

        await server.stop()
        logger.info("The Server has been stopped.")






# 同步入口
def run() -> None:
    asyncio.run(coreApp().run())