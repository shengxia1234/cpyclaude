import asyncio
import sys
import time
import json
import cpy_Claude
from cpy_Claude.core.config import config
from cpy_Claude.core.bus.envelope import JsonRpcError,JsonRpcSuccess


def cmd_ping(config : config):
    try:
        asyncio.run(_ping(config)) #在同步进程中启动协程
    except (ConnectionRefusedError,OSError):
        print(f"error : core is not running({config.host}:{config:port})",file=sys.stderr)
        sys.exit(1)


async def _ping(config : config):
    beg = time.monotonic()
    reader,writer = await asyncio.open_connection(config.host,config.port)

    req = {
        "jsonrpc" : "2.0",
        "id" : "cli_1",
        "method" : "core.ping",
        "params" : {"client": f"cli/{cpy_Claude.__version__}"},
    }

    writer.write((json.dump(req) + "\n").encode())
    await writer.drain()

    try:
        line = await asyncio.wait_for(reader.readline(),timeout=10.0)
    except (TimeoutError):
        print("ping timeout:10.0s")
        sys.exit(1)

    end = time.monotonic()
    latency_ms = int((end - beg) * 1000)

    writer.close()
    await writer.wait_closed()

    raw = json.load(line)
    if "error" in raw:
        e = JsonRpcError.model_validate_json(raw) # 导入json初始化类
        errorobj = e.error
        print(f"_ping func error happens:code({errorobj.code}),message({errorobj.message}),data({errorobj.data})",file=sys.stderr)

    res = JsonRpcSuccess.model_validate_json(raw)
    print(f"ping success,latency:{latency_ms}ms",file=sys.stdout)

