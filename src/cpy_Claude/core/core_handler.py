import logging
import cpy_Claude
import datetime
import time

from typing import Any
from cpy_Claude.core.bus.commands import PongResult
from collections.abc import Callable

# 从coreApp中获取必要属性,不执行内部其他方法
from cpy_Claude.core.app import coreApp


logger = logging.getLogger(__name__)

# 传入dict[str,Any],返回Any
class coreHandler:
    # 处理ping命令
    async def ping_handler(self,params : dict[str,Any]):
        client = params.get("client", "unknown")
        logger.debug("ping from %s", client)
        return PongResult(
            server_version=cpy_Claude.__version__,
            uptime_ms=int((time.monotonic() - coreApp.start_time) * 1000),
            received_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )