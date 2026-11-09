from __future__ import annotations

import datetime
import asyncio

from cpy_Claude.core.config import config
from cpy_Claude.core.llm.base import LLMProvider
from cpy_Claude.core.llm.provider import AnthropicProvider,OpenAIProvider
from cpy_Claude.core.events.bus import EventHandler,EventBus
from cpy_Claude.core.tools import TOOLS
from cpy_Claude.core.loop import AgentLoop
from cpy_Claude.core.context import ExecutionContext
from cpy_Claude.core.bus.events import RunStartEvent,RunFinishEvent
from cpy_Claude.core.tools.invocation import invoke_tool
from cpy_Claude.core.runs import new_run_id,events_file
from cpy_Claude.core.runs import RUNS_DIR
from cpy_Claude.core.events.writer import EventWriter

from pathlib import Path

tz = datetime.timezone(datetime.timedelta(hours=8))

def _now() -> str:
    return datetime.datetime.now(tz).isoformat()

class AgentRunner:
    def __init__(self,cf : config,*,provider : LLMProvider | None = None,runs_dir : Path | None = None,extra_handlers : list[EventHandler],bus : EventBus | None):
        self._config = cf
        self._provider = provider
        self._extra_handlers : list[EventHandler] = extra_handlers or []
        self._runs_dir = runs_dir or RUNS_DIR
        self._bus = bus

    async def run(self,goal : str,rid : str | None):
        run_id : str = rid or new_run_id()
        run_path = self._runs_dir / run_id
        run_path.mkdir(parents=True,exist_ok=True)

        # eventbus由core管理，从外部传入
        bus = self._bus if self._bus is not None else EventBus()
        context = ExecutionContext(run_id=run_id,goal=goal,step_max=self._config.LLM.max_steps,which_api=self._config.LLM.which_api)

        async with EventWriter(events_file(run_id)) as ew:
            ew.subscribe(bus)
            await bus.publish(RunStartEvent(run_id=run_id,goal=goal,ts=_now()))
            for handler in self._extra_handlers:
                bus.subscribe(handler)
            tools = TOOLS
            if self._provider is None:
                if self._config.LLM.which_api == "anthropic":
                    self._provider = AnthropicProvider(self._config.LLM.model)
                else:
                    self._provider = OpenAIProvider(self._config.LLM.model)
            agent_loop = AgentLoop(self._provider,tools,bus)
            cancelled = False
            try:
                await agent_loop.loop(context)
            except asyncio.CancelledError:
                cancelled = True
                if context.is_done:
                    context.mark_failed("cancelled")
            await bus.publish(RunFinishEvent(run_id=run_id,status=context.status,reason=context.reason,step=context.step_now,ts=_now()))
        if cancelled:
            # 重新抛出，否则无效
            raise asyncio.CancelledError
