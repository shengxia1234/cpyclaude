from __future__ import annotations

import logging
import asyncio
import uuid
import fnmatch
import json
import datetime

from dataclasses import dataclass
from cpy_Claude.core.bus.events import BaseEvent
from cpy_Claude.core.bus.envelope import EventPushEnvelope
from cpy_Claude.core.trace.writer import TraceWriter,TraceRecord

logger = logging.getLogger(__name__)

tz = datetime.timezone(datetime.timedelta(hours=8))
def _now() -> str:
    return datetime.datetime.now(tz).isoformat()

@dataclass
class _Subscription:
    sub_id : str
    writer: asyncio.StreamWriter
    topics: list[str]
    scope: str

class IpcEventBoardCaster:
    def __init__(self,trace_writer : TraceWriter | None = None):
        self._subscription : list[_Subscription] = []
        self._trace = trace_writer

    def subscribe(self,writer : asyncio.StreamWriter,topics : list[str],scope : str) -> str:
        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        self._subscription.append(_Subscription(
            sub_id=sub_id,
            writer=writer,
            topics=topics,
            scope=scope
        ))
        return sub_id

    def unsubscribe(self,writer : asyncio.StreamWriter):
        self._subscription = [s for s in self._subscription if s.writer is not writer]

    async def handle(self,event : BaseEvent):
        event_dict = event.model_dump()
        run_id : str = event_dict.get("run_id","")
        event_type : str = event_dict.get("type","")

        dead : list[asyncio.StreamWriter] = []

        for sub in self._subscription:
            if not self._match_scope(run_id,sub.scope):
                continue
            if not self._match_topics(sub.topics,event_type):
                continue
            try:
                envelope = EventPushEnvelope(event=event.model_dump())
                sub.writer.write(envelope.model_dump_json().encode() + b"\n")
                await sub.writer.drain()
                if self._trace is not None:
                    client_id = sub.writer.get_extra_info("peername","<unknown>")
                    self._trace.emit(TraceRecord(
                        ts=_now(),
                        direction="CORE->CLIENT",
                        layer="ipc",
                        kind="push",
                        run_id=run_id,
                        client_id=str(client_id),
                        data={"sub_id": sub.sub_id,"event_type": event.type}
                    ))
            except (ConnectionResetError,BrokenPipeError,OSError):
                logger.debug("dead connection for sub %s, scheduling cleanup", sub.sub_id)
                dead.append(sub.writer)

        for d in dead:
            self.unsubscribe(d)


    @staticmethod
    def _match_topics(topics : list[str],event_type : str):
        return any(fnmatch.fnmatch(event_type,topic) for topic in topics)

    @staticmethod
    def _match_scope(run_id : str,scope : str):
        if scope == "global":
            return True
        if scope.startswith("run:"):
            return run_id == scope[4:]
        return False