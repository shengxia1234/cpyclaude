import time
import asyncio
import logging

from cpy_Claude.core.core_handler import coreHandler
from cpy_Claude.core.transport.socket_server import SocketServer
from cpy_Claude.core.config import get_config

logger = logging.getLogger(__name__)

class coreApp:
    def __init__(self) -> None:
        self._start_time = time.monotonic()

    async def run(self) -> None:
        self._start_time = time.monotonic()

        config = get_config()
        server = SocketServer(config.host,config.port)
        server.register("core.ping",coreHandler.ping_handler)

    @property
    def start_time(self) -> float:
        return self._start_time





# 同步入口
def run() -> None:
    asyncio.run(coreApp().run())