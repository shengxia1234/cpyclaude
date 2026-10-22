from cpy_Claude.core.config import config

class StdoutPrinter:
    # 订阅事件总线并将运行进度格式化打印到终端
    def __init__(self):
        self._inline = False
        ...

    def _ensure_newline(self):
        if self._inline:
            print()
            self._inline = False

    async def handle(self):
        ...

def cmd_run(goal : str,cf : config):
    Printer = StdoutPrinter()
    ...