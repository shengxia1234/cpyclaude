from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any, Protocol

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Label, Static

from cpy_Claude.core.transport.socket_client import IpcError, SocketClient

_RETRY_SECONDS = 2
_TOPICS = ["run.*", "step.*", "tool.*", "llm.token", "llm.usage", "log.*"]


class TuiConfig(Protocol):
    @property
    def host(self) -> str: ...

    @property
    def port(self) -> int: ...


def _preview(text: str, limit: int = 60) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[:limit] + "…"


class LLMStreamBlock(Static):
    """将连续的模型输出写入同一个文本组件。"""

    DEFAULT_CSS = "LLMStreamBlock { height: auto; padding: 0 1; }"

    def __init__(self, token: str = "") -> None:
        super().__init__(token, markup=False)
        self._text = token

    def append_token(self, token: str) -> None:
        self._text += token
        self.update(self._text)


class ToolCallBlock(Widget):
    """折叠时显示摘要，展开后显示参数、结果和耗时。"""

    can_focus = True
    BINDINGS = [
        Binding("enter", "toggle_details", "Toggle details", show=False),
        Binding("space", "toggle_details", "Toggle details", show=False),
    ]
    DEFAULT_CSS = """
    ToolCallBlock { height: auto; padding: 0 1; }
    ToolCallBlock:focus > .summary { background: $boost; }
    ToolCallBlock > .detail { display: none; padding: 0 2; }
    ToolCallBlock.expanded > .detail { display: block; }
    """

    def __init__(self, tool_name: str, params: dict[str, Any] | None) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.params = params
        self.result: str | None = None
        self.elapsed_ms: int | None = None
        self.error: str | None = None
        self.error_type: str | None = None
        self._finished = False

    def compose(self) -> ComposeResult:
        yield Static(self._summary(), classes="summary")
        yield Static(self._details(), classes="detail")

    def _summary(self) -> Text:
        arrow = "▾" if self.has_class("expanded") else "▸"
        text = Text.assemble((f"{arrow} ", "dim"), (self.tool_name, "bold yellow"))
        if self.params:
            args = _preview(json.dumps(self.params, ensure_ascii=False))
            text.append(f"  {args}", style="dim")
        if not self._finished:
            text.append("  running…", style="dim")
            return text

        if self.error is not None:
            text.append("  ✗ failed", style="red")
            if self.error:
                text.append(f"  {_preview(self.error)}", style="red")
        else:
            text.append("  ✓ completed", style="green")
            if self.result:
                text.append(f"  {_preview(self.result)}", style="dim")
        if self.elapsed_ms is not None:
            text.append(f"  {self.elapsed_ms} ms", style="dim")
        return text

    def _details(self) -> Text:
        text = Text("Parameters\n", style="dim")
        params = (
            json.dumps(self.params, ensure_ascii=False, indent=2)
            if self.params is not None
            else "(start event unavailable)"
        )
        text.append(params)
        if not self._finished:
            return text

        if self.error is not None:
            heading = f"Error ({self.error_type})" if self.error_type else "Error"
            text.append(f"\n{heading}\n", style="bold red")
            text.append(self.error or "(no message)")
        else:
            text.append("\nResult\n", style="bold")
            text.append(self.result or "(empty)")
        if self.elapsed_ms is not None:
            text.append(f"\nElapsed  {self.elapsed_ms} ms", style="dim")
        return text

    def set_result(
        self,
        *,
        result: str | None = None,
        elapsed_ms: int | None = None,
        error: str | None = None,
        error_type: str | None = None,
    ) -> None:
        self.result = result
        self.elapsed_ms = elapsed_ms
        self.error = error
        self.error_type = error_type
        self._finished = True
        # 回放时，完成事件可能先于组件挂载。compose 会读取最新状态。
        if self.children:
            self.query_one(".summary", Static).update(self._summary())
            self.query_one(".detail", Static).update(self._details())

    def action_toggle_details(self) -> None:
        self.toggle_class("expanded")
        self.query_one(".summary", Static).update(self._summary())

    def on_click(self) -> None:
        self.action_toggle_details()


class TuiApp(App[None]):
    TITLE = "cpy_Claude"
    BINDINGS = [Binding("q", "quit", "Quit")]
    CSS = """
    Screen { layout: vertical; }
    #header { height: 1; background: $primary; color: $text; padding: 0 1; }
    #log { height: 1fr; border: round $primary; padding: 0 1; }
    #log > Static { height: auto; padding: 0 1; }
    #log > .run-start { padding-top: 1; }
    #log > .run-finish { padding-bottom: 1; }
    """

    def __init__(self, host: str, port: int, replay_run_id: str | None = None) -> None:
        super().__init__()
        self._host = host
        self._port = port
        self._replay_run_id = replay_run_id
        self._current_llm: LLMStreamBlock | None = None
        self._current_llm_run_id: str | None = None
        self._pending_tool_blocks: dict[str, ToolCallBlock] = {}

    def compose(self) -> ComposeResult:
        yield Label(f"{self.TITLE}  ● connecting…", id="header", markup=False)
        yield VerticalScroll(id="log")

    def on_mount(self) -> None:
        self.run_worker(self._socket_loop(), exclusive=True, name="socket")

    def _append(self, widget: Widget) -> None:
        log = self.query_one("#log", VerticalScroll)
        follow = log.is_vertical_scroll_end
        log.mount(widget)
        if follow:
            log.scroll_end(animate=False)

    def _break_llm(self) -> None:
        self._current_llm = None
        self._current_llm_run_id = None

    async def _socket_loop(self) -> None:
        header = self.query_one("#header", Label)

        async def on_event(event: dict[str, Any]) -> None:
            self._handle_event(event)

        while True:
            client = SocketClient(self._host, self._port)
            try:
                await client.connect()
            except OSError:
                header.update(f"{self.TITLE}  ● not connected — retrying in {_RETRY_SECONDS}s")
                await asyncio.sleep(_RETRY_SECONDS)
                continue

            client.on_event(on_event)
            header.update(f"{self.TITLE}  ● connected  {self._host}:{self._port}")

            params: dict[str, Any] = {"topics": _TOPICS, "scope": "global"}
            if self._replay_run_id is not None:
                params["replay_from_run"] = self._replay_run_id

            reader = asyncio.create_task(client.run_event_loop())
            subscribing = asyncio.create_task(client.send_command("event.subscribe", params))
            status = "disconnected"
            try:
                # 若先收到 EOF，不等待可能无法再返回的订阅响应。
                done, _ = await asyncio.wait(
                    (reader, subscribing), return_when=asyncio.FIRST_COMPLETED
                )
                if subscribing in done and not subscribing.cancelled():
                    await subscribing
                await reader
            except (IpcError, OSError) as exc:
                status = f"connection error — {exc}"
            finally:
                for task in (reader, subscribing):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(reader, subscribing, return_exceptions=True)
                self._break_llm()
                with suppress(OSError):
                    await client.close()

            header.update(f"{self.TITLE}  ● {status} — retrying in {_RETRY_SECONDS}s")
            await asyncio.sleep(_RETRY_SECONDS)

    def _handle_token(self, event: dict[str, Any]) -> None:
        token = event.get("token")
        if not token:
            return

        run_id = event.get("run_id")
        if self._current_llm is None or self._current_llm_run_id != run_id:
            self._current_llm = LLMStreamBlock(token)
            self._current_llm_run_id = run_id
            self._append(self._current_llm)
            return

        log = self.query_one("#log", VerticalScroll)
        follow = log.is_vertical_scroll_end
        self._current_llm.append_token(token)
        if follow:
            log.scroll_end(animate=False)

    def _handle_tool(self, event_type: str, event: dict[str, Any]) -> None:
        tool_id = event.get("tool_id")
        tool_key = str(tool_id) if tool_id is not None else ""
        tool_name = event.get("tool_name") or "tool"

        if event_type == "tool.call_start":
            block = ToolCallBlock(tool_name, event.get("params") or {})
            if tool_key:
                self._pending_tool_blocks[tool_key] = block
            self._append(block)
            return

        block = self._pending_tool_blocks.pop(tool_key, None)
        has_start = block is not None
        if block is None:
            # 实时订阅可能在工具开始之后才建立。
            block = ToolCallBlock(tool_name, None)

        elapsed_ms = event.get("elapsed_ms")
        if event_type == "tool.call_fail":
            block.set_result(
                elapsed_ms=elapsed_ms,
                error=event.get("error_msg") or event.get("error_message") or "",
                error_type=event.get("error_type"),
            )
        else:
            result = event.get("output", event.get("result"))
            block.set_result(
                result=str(result) if result is not None else "",
                elapsed_ms=elapsed_ms,
            )
        if not has_start:
            self._append(block)

    def _handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type", "")
        if event_type == "llm.token":
            self._handle_token(event)
            return

        if event_type in {"step.finish", "step.finished"}:
            self._break_llm()
            return

        if event_type in {"tool.call_start", "tool.call_finish", "tool.call_fail"}:
            self._break_llm()
            self._handle_tool(event_type, event)
            return

        if event_type == "run.start":
            line = Text.assemble(
                ("▶ run  ", "bold cyan"),
                (str(event.get("run_id", "")), "dim"),
                f"\n  goal: {event.get('goal', '')}",
            )
            classes = "run-start"
        elif event_type == "step.start":
            line = Text(f"── step {event.get('step', '')}", style="dim")
            classes = "step-start"
        elif event_type == "run.finish":
            status = event.get("status", "")
            steps = event.get("step", event.get("steps", 0))
            outcome = "✓ completed" if status == "success" else f"✗ {status or 'failed'}"
            color = "bold green" if status == "success" else "bold red"
            line = Text.assemble((outcome, color), (f"  {steps} steps", "dim"))
            if reason := event.get("reason"):
                line.append(f"  {reason}", style="dim")
            classes = "run-finish"
        elif event_type == "llm.usage":
            line = Text(
                f"tokens  in={event.get('input_tokens', 0)}  "
                f"out={event.get('output_tokens', 0)}  "
                f"cache_read={event.get('cache_read_input_tokens', 0)}",
                style="dim",
            )
            classes = "usage"
        elif event_type == "log.line":
            level = str(event.get("level") or "INFO")
            color = {"ERROR": "bold red", "WARNING": "yellow"}.get(level, "dim")
            line = Text.assemble(
                (level, color),
                (f"  {event.get('source', '')}  ", "dim"),
                str(event.get("message", "")),
            )
            classes = "log-line"
        else:
            return

        self._break_llm()
        self._append(Static(line, classes=classes))


def run(config: TuiConfig, replay_run_id: str | None = None) -> None:
    TuiApp(config.host, config.port, replay_run_id=replay_run_id).run()
