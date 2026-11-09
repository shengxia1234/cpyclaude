from __future__ import annotations

import asyncio
import json
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import Resize

from textual.scrollbar import (
    ScrollBar,
    ScrollTo,
    ScrollUp,
    ScrollDown,
)

# 保留之前的组件导入
from textual.widgets import RichLog, Label

from cpy_Claude.core.transport.socket_client import IpcError, SocketClient


class VerticalLogScrollBar(ScrollBar):
    """独立于日志边框外的垂直滚动条"""

    def __init__(self) -> None:
        super().__init__(
            vertical=True,
            name="log-scrollbar",
        )
        self._target: ExternalRichLog | None = None

    def set_target(self, target: ExternalRichLog) -> None:
        """绑定日志组件"""
        self._target = target

    def on_scroll_to(self, message: ScrollTo) -> None:
        """拖动滑块：关闭动画，立即更新"""

        if self._target is None or message.y is None:
            return

        log = self._target

        # 限制目标滚动位置
        target_y = max(
            0.0,
            min(message.y, log.max_scroll_y),
        )

        # 用户查看历史内容时暂停自动滚动
        # 回到最底部时恢复
        log.auto_scroll = (
            target_y >= log.max_scroll_y - 1
        )

        # 立即滚动，不执行动画
        log.scroll_to(
            y=target_y,
            animate=False,
            immediate=True,
        )

        message.stop()

    def on_scroll_up(self, message: ScrollUp) -> None:
        """点击滑块上方，向上翻页"""

        if self._target is not None:
            self._target.auto_scroll = False
            self._target.scroll_page_up(
                animate=False,
            )

        message.stop()

    def on_scroll_down(self, message: ScrollDown) -> None:
        """点击滑块下方，向下翻页"""

        if self._target is not None:
            self._target.scroll_page_down(
                animate=False,
            )

        message.stop()


class ExternalRichLog(RichLog):
    """支持外部滚动条、自动换行和即时滚动的日志组件"""

    def __init__(self, **kwargs: Any) -> None:

        # 自动换行
        kwargs.setdefault("wrap", True)

        # 允许日志适应较窄终端
        kwargs.setdefault("min_width", 1)

        # 默认自动滚动至底部
        kwargs.setdefault("auto_scroll", True)

        super().__init__(**kwargs)

        self._external_scrollbar: VerticalLogScrollBar | None = None

        # 防止重复安排滚动条同步
        self._sync_pending = False

    def attach_scrollbar(
        self,
        scrollbar: VerticalLogScrollBar,
    ) -> None:
        """绑定外部滚动条"""

        self._external_scrollbar = scrollbar
        self._schedule_scrollbar_sync()

    def _schedule_scrollbar_sync(self) -> None:
        """只安排一次完整同步，避免重复刷新"""

        if not self.is_mounted:
            return

        if self._external_scrollbar is None:
            return

        if self._sync_pending:
            return

        self._sync_pending = True

        self.call_after_refresh(
            self._sync_scrollbar
        )

    def _sync_scrollbar(self) -> None:
        """同步滚动条尺寸和位置"""

        self._sync_pending = False

        bar = self._external_scrollbar

        if (
            bar is None
            or not self.is_mounted
            or not bar.is_mounted
        ):
            return

        # 日志内容总高度
        content_height = max(
            1,
            self.virtual_size.height,
        )

        # 当前可视区域高度
        viewport_height = max(
            1,
            self.scrollable_content_region.height,
        )

        # 仅在完整同步时更新尺寸
        if bar.window_virtual_size != content_height:
            bar.window_virtual_size = content_height

        if bar.window_size != viewport_height:
            bar.window_size = viewport_height

        # 同步当前滚动位置
        if bar.position != self.scroll_y:
            bar.position = self.scroll_y

        # 不主动调用 bar.refresh()
        # 响应式属性变化会触发必要的刷新

    def watch_scroll_y(
        self,
        old_value: float,
        new_value: float,
    ) -> None:
        """滚动时直接更新滑块，不安排额外刷新"""

        super().watch_scroll_y(old_value, new_value)

        bar = self._external_scrollbar

        if bar is not None and bar.is_mounted:
            if bar.position != new_value:
                bar.position = new_value

        # 用户离开底部时停止自动滚动
        # 回到底部时恢复
        self.auto_scroll = (
            new_value >= self.max_scroll_y - 1
        )

    def watch_virtual_size(
        self,
        old_value,
        new_value,
    ) -> None:
        """内容总高度改变时同步尺寸"""

        self._schedule_scrollbar_sync()

    def on_resize(self, event: Resize) -> None:
        """终端窗口尺寸变化时重新同步"""

        super().on_resize(event)

        self._schedule_scrollbar_sync()


class LogPane(Horizontal):
    """日志区域 + 边框外的独立垂直滚动条"""

    def compose(self) -> ComposeResult:

        # 日志组件
        yield ExternalRichLog(
            id="log",
            highlight=True,
            markup=True,
            wrap=True,
            min_width=1,
            auto_scroll=True,
            max_lines=5000,
        )

        # 独立垂直滚动条
        yield VerticalLogScrollBar()

    def on_mount(self) -> None:

        # ===== 获取组件 =====

        self._log_widget = self.query_one(
            "#log",
            ExternalRichLog,
        )

        self._scrollbar_widget = self.query_one(
            VerticalLogScrollBar,
        )

        # ===== LogPane 布局 =====

        self.styles.width = "1fr"
        self.styles.height = "1fr"

        # ===== 日志组件 =====

        log = self._log_widget

        log.styles.width = "1fr"
        log.styles.height = "1fr"

        # 圆角边框
        log.styles.border = ("round", "blue")

        # 内边距
        log.styles.padding = (1, 1)

        # 隐藏内部滚动条
        log.styles.scrollbar_visibility = "hidden"

        # 内部滚动条不占据空间
        log.styles.scrollbar_size_vertical = 0
        log.styles.scrollbar_size_horizontal = 0

        # 不允许水平滚动
        log.styles.overflow_x = "hidden"

        # 保持垂直滚动能力
        log.styles.overflow_y = "auto"

        # ===== 外部滚动条 =====

        bar = self._scrollbar_widget

        bar.styles.width = 1
        bar.styles.height = "1fr"

        # 与边框间隔一列
        bar.styles.margin = (0, 0, 0, 1)

        # 始终保留滚动条占用的宽度
        # 避免显示状态变化时引发布局抖动
        # 内容不足一页时，滚动条没有活动滑块

        # ===== 组件绑定 =====

        bar.set_target(log)
        log.attach_scrollbar(bar)

        # ===== 初次同步 =====

        log._schedule_scrollbar_sync()



class TuiApp(App[None]):
    TITLE = "KamaClaude TUI"
    BINDINGS = [Binding("q", "quit", "Quit")]
    CSS = """
           Screen {
            layout: vertical;
        }

        #status {
            height: 1;
            background: $primary;
            color: $text;
            padding: 0 1;
        }
    """
    def __init__(self,host : str,port : int,replay_run_id : str | None = None):
        super().__init__()
        self._host = host
        self._port = port
        self._replay_run_id = replay_run_id
        self._token_buf = ""

    # 构建 UI：顶部状态栏 + 可滚动事件日志
    def compose(self) -> ComposeResult:
        # yield:让一个函数变成可暂停和可恢复的函数，而不是一次性执行完就返回
        yield Label("● connecting...", id="status")
        yield LogPane()

    # 挂载后启动 socket 连接 worker
    def on_mount(self) -> None:
        self.run_worker(self._socket_loop(), exclusive=True, name="socket")

    # 管理 SocketClient 生命周期：连接、订阅、接收事件、断线重连
    async def _socket_loop(self) -> None:
        log = self.query_one("#log", RichLog)
        status = self.query_one("#status", Label)

        while True:
            client = SocketClient(self._host, self._port)
            try:
                await client.connect()
            except (ConnectionRefusedError, OSError):
                status.update("● not connected — retrying in 2s")
                await asyncio.sleep(2)
                continue

            status.update(f"● connected  {self._host}:{self._port}")
            loop_task = asyncio.create_task(client.run_event_loop())

            async def on_event(event: dict[str, Any]) -> None:
                self._handle_event(event, log)

            client.on_event(on_event)

            try:
                params: dict[str, Any] = {
                    "topics": [
                        "run.*", "step.*", "tool.*",
                        "llm.token", "llm.usage", "log.*",
                    ],
                    "scope": "global",
                }
                if self._replay_run_id is not None:
                    params["replay_from_run"] = self._replay_run_id
                await client.send_command("event.subscribe", params)
                await loop_task
            except IpcError as e:
                status.update(f"● subscribe error — {e}")
            finally:
                if not loop_task.done():
                    loop_task.cancel()
                self._flush_tokens(log)
                await client.close()

            status.update("● disconnected — retrying in 2s")
            await asyncio.sleep(2)

    # 将 llm.token 累积缓冲区写入日志并清空
    def _flush_tokens(self, log: RichLog) -> None:
        if self._token_buf:
            log.write(self._token_buf)
            self._token_buf = ""

    # 根据事件 type 字段格式化并写入 RichLog，llm.token 累积后整体写入
    def _handle_event(self, event: dict[str, Any], log: RichLog) -> None:
        t = event.get("type", "")
        if t == "llm.token":
            self._token_buf += event.get("token", "")
            return

        self._flush_tokens(log)

        if t == "run.start":
            log.write(
                f"[bold blue]▶ run[/bold blue]  {event.get('run_id', '')}  "
                f"{event.get('goal', '')}"
            )
        elif t == "step.start":
            log.write(f"[bold]  step {event.get('step')}[/bold]  planning...")
        elif t == "tool.call_start":
            params_str = json.dumps(event.get("params", {}), ensure_ascii=False)
            log.write(f"[green]  tool[/green]  {event.get('tool_name', '')}  {params_str}")
        elif t == "tool.call_finish":
            log.write(
                f"[green]  tool[/green]  {event.get('tool_name', '')} "
                f"✓  {event.get('elapsed_ms')}ms"
            )
        elif t == "tool.call_fail":
            log.write(
                f"[red]  tool[/red]  {event.get('tool_name', '')} "
                f"✗  {event.get('error_message', '')}"
            )
        elif t == "step.finish":
            log.write(f"  step {event.get('step')}  done")
        elif t == "run.finish":
            s = event.get("status", "")
            color = "green" if s == "success" else "red"
            log.write(f"[{color}]■ run[/{color}]  {s}  {event.get('steps')} steps")
        elif t == "llm.usage":
            log.write(
                f"[dim]  usage[/dim]  in={event.get('input_tokens')} "
                f"out={event.get('output_tokens')} "
                f"cache_read={event.get('cache_read_input_tokens')}"
            )
        elif t == "log.line":
            level = event.get("level", "INFO")
            log.write(
                f"[dim]{level}[/dim]  {event.get('source', '')}  {event.get('message', '')}"
            )
