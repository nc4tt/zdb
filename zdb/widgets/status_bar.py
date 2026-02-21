"""Status indicator widget with animated spinner."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from zdb.backend import CmdStatus
from zdb.widgets.ascii_art import LOADING_FRAMES


class StatusIndicator(Static):
    """Displays status with animated spinner for RUNNING state."""

    status: reactive[CmdStatus] = reactive(CmdStatus.IDLE)
    _frame: int = 0
    _timer = None

    STATUS_MAP = {
        CmdStatus.IDLE: ("○", "status-running", "Idle"),
        CmdStatus.RUNNING: ("", "status-running", "Running..."),
        CmdStatus.SUCCESS: ("✓", "status-success", "Success"),
        CmdStatus.FAILED: ("✗", "status-failed", "Failed"),
        CmdStatus.AUTH_REQUIRED: ("🔒", "status-auth", "Auth Required"),
    }

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.1, self._animate)

    def _animate(self) -> None:
        if self.status == CmdStatus.RUNNING:
            self._frame = (self._frame + 1) % len(LOADING_FRAMES)
            self._render_status()

    def watch_status(self, new_status: CmdStatus) -> None:
        self._render_status()

    def _render_status(self) -> None:
        icon, css_class, label = self.STATUS_MAP.get(
            self.status, ("?", "", "Unknown")
        )
        if self.status == CmdStatus.RUNNING:
            icon = LOADING_FRAMES[self._frame]

        self.remove_class("status-running", "status-success", "status-failed", "status-auth")
        self.add_class(css_class)
        self.update(f" {icon} {label}")
