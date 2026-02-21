"""Command output panel widget with auto-scroll and rich formatting."""

from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.widgets import RichLog

from zdb.backend import CmdStatus


class CommandOutput(RichLog):
    """Rich log panel for displaying command execution output."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            min_width=40,
            **kwargs,
        )

    def log_command(self, cmd: str) -> None:
        """Log a command being executed."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(Text(f"[{ts}] $ {cmd}", style="bold #4fc3f7"))

    def log_output(self, output: str, status: CmdStatus = CmdStatus.SUCCESS) -> None:
        """Log command output with status-based coloring."""
        if not output.strip():
            return

        style_map = {
            CmdStatus.SUCCESS: "#66bb6a",
            CmdStatus.FAILED: "#ef5350",
            CmdStatus.AUTH_REQUIRED: "#ffa726",
            CmdStatus.RUNNING: "#4fc3f7",
        }
        color = style_map.get(status, "#c9d1d9")

        for line in output.splitlines():
            self.write(Text(f"  {line}", style=color))

    def log_status(self, message: str, status: CmdStatus) -> None:
        """Log a status message."""
        icons = {
            CmdStatus.SUCCESS: "✓",
            CmdStatus.FAILED: "✗",
            CmdStatus.AUTH_REQUIRED: "🔒",
            CmdStatus.RUNNING: "⟳",
        }
        icon = icons.get(status, "•")
        style_map = {
            CmdStatus.SUCCESS: "bold #66bb6a",
            CmdStatus.FAILED: "bold #ef5350",
            CmdStatus.AUTH_REQUIRED: "bold #ffa726",
            CmdStatus.RUNNING: "bold #4fc3f7",
        }
        style = style_map.get(status, "#c9d1d9")
        self.write(Text(f"  {icon} {message}", style=style))
        self.write(Text(""))  # blank line separator
