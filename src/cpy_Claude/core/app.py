import time
import asyncio
import logging
import signal
import cpy_Claude
import datetime

from cpy_Claude.core.transport.socket_server import SocketServer
from cpy_Claude.core.bus.commands import PongResult
from cpy_Claude.core.config import get_config
from cpy_Claude.core.logging_setup import setup_logging
from typing import Any

logger = logging.getLogger(__name__)

class coreApp:
    def __init__(self) -> None:
        self._start_time = time.monotonic()

    async def _ping_handler(self,params : dict[str,Any]):
        client = params.get("client", "unknown")
        logger.debug("ping from %s", client)
        tz = datetime.timezone(datetime.timedelta(hours=8))
        return PongResult(
            server_version=cpy_Claude.__version__,
            uptime_ms=int((time.monotonic() - self._start_time) * 1000),
            received_at=datetime.datetime.now(tz).isoformat(),
        )

    async def run(self) -> None:
        self._start_time = time.monotonic()

        cf = get_config()
        setup_logging(cf)
        server = SocketServer(cf.host,cf.port)
        server.register("core.ping",self._ping_handler)

        #启动服务器
        host_port = await server.start()
        logger.info("cpy_Claude Server is now running on %s:%d",cf.host,cf.port)

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