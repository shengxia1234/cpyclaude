# 推迟类型注解,可以让类型注解引用暂时还未被定义的类
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from cpy_Claude.core.config import config

_TEXT_FMT = 'level=%(levelname)s ts=%(asctime)s source=%(name)s msg="%(message)s"'
_JSON_FMT = '{"level":"%(levelname)s","ts":"%(asctime)s","source":"%(name)s","msg":"%(message)s"}'

# 设置根root logger,root的设置可以影响所有子logger的设置
def setup_logging(cf : config):
    #获取logging的级别，没有默认info
    level = getattr(logging, cf.logging.level.upper(), logging.INFO)
    fmt = _JSON_FMT if config.logging.format == "json" else _TEXT_FMT
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)
    # 清空handler,并关闭handler持有的资源
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    if cf.logging.file:
        log_path = Path(config.logging.file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)