from pydantic import BaseModel,Discriminator
from typing import Literal,Annotated

class PingCommand(BaseModel):
    type: Literal["core.ping"] = "core.ping"
    client: str

class PongResult(BaseModel):
    server_version: str
    uptime_ms: int
    received_at: str  # ISO 8601

# agent启动命令
class AgentRunCommand(BaseModel):
    type: Literal["agent.run"] = "agent.run"
    goal: str

# res马上返回，运行结果由事件流给出
class AgentRunResult(BaseModel):
    run_id: str

# 订阅事件命令
class EventSubscribeCommand(BaseModel):
    type: Literal["event.subscribe"] = "event.subscribe"
    topics: list[str] # 事件过滤
    scope: str = "global" # 限制运行范围
    replay_from_run: str | None = None # 指定需要回放的历史运行

class EventSubscribeResult(BaseModel):
    subscription_id: str # 订阅编号
    replayed_count: int = 0 # 本次回放事件数量

# 根据 type 字段决定命令类型的判别联合,可以解析成type对应的类型
Command = Annotated[
    PingCommand,
    AgentRunCommand,
    EventSubscribeCommand,
    Discriminator("type"),
]
