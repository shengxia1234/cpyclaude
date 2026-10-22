from typing import Callable,Awaitable,Any
from cpy_Claude.core.bus.events import Event

type EventHandler = Callable[[Event],Awaitable[Any]]

# 订阅者将回调函数注册到Bus上
class EventBus:
    def __init__(self):
        self.handlers : list[EventHandler] = []

    # 订阅
    def subscribe(self,handler : EventHandler):
        self.handlers.append(handler)
    # 发布
    async def publish(self,event : Event):
        for handler in self.handlers:
            await handler(event)