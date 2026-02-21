"""Animated splash/intro screen with glitch-reveal effect and boot sequence."""

from __future__ import annotations

import random

from textual.app import ComposeResult
from textual.containers import Center, Container, Vertical
from textual.screen import Screen
from textual.widgets import ProgressBar, Static

from zdb.widgets.ascii_art import BOOT_SEQUENCE, LOGO

GLITCH_CHARS = "░▒▓█▄▀■□▪▫●◆◇◈"


class SplashScreen(Screen):
    """Animated intro screen with glitch-reveal effect."""

    BINDINGS = [("escape", "skip", "Skip intro")]
    AUTO_FOCUS = None

    def compose(self) -> ComposeResult:
        with Container(id="splash-screen"):
            with Vertical(id="splash-container"):
                yield Static("", id="ascii-logo")
                yield Static("v6", id="splash-version")
                yield Static("Android Debug Bridge & Fastboot", id="splash-subtitle")
                with Center():
                    yield ProgressBar(
                        total=len(BOOT_SEQUENCE),
                        show_eta=False,
                        show_percentage=True,
                        id="splash-progress",
                    )
                yield Static("", id="splash-status")
                yield Static("Press [bold]ESC[/bold] to skip", id="splash-hint")

    async def on_mount(self) -> None:
        """Start the glitch-reveal animation sequence."""
        self._logo_lines = LOGO.lstrip("\n").split("\n")
        self._revealed: list[str] = [""] * len(self._logo_lines)
        self._current_line = 0
        self._glitch_tick_count = 0
        self._boot_step = 0
        self._boot_started = False

        # Start glitch-reveal animation
        self.set_interval(0.06, self._glitch_reveal_tick)

    def _glitch_reveal_tick(self) -> None:
        """Reveal logo lines with a glitch scramble effect."""
        if self._current_line >= len(self._logo_lines):
            # Logo fully revealed — kick off boot sequence once
            if not self._boot_started:
                self._boot_started = True
                self.set_interval(0.4, self._boot_tick)
            return

        target = self._logo_lines[self._current_line]
        self._glitch_tick_count += 1

        # Each line gets 4 glitch frames, then resolves
        if self._glitch_tick_count <= 4:
            # Generate glitch version of the line
            glitched = ""
            for ch in target:
                if ch == " ":
                    glitched += " "
                else:
                    glitched += random.choice(GLITCH_CHARS)
            self._revealed[self._current_line] = glitched
        else:
            # Resolve to the actual line
            self._revealed[self._current_line] = target
            self._current_line += 1
            self._glitch_tick_count = 0

        logo_widget = self.query_one("#ascii-logo", Static)
        logo_widget.update("\n".join(self._revealed))

    def _boot_tick(self) -> None:
        """Advance through the boot sequence messages."""
        if self._boot_step < len(BOOT_SEQUENCE):
            status = self.query_one("#splash-status", Static)
            progress = self.query_one("#splash-progress", ProgressBar)

            msg = BOOT_SEQUENCE[self._boot_step]
            status.update(f"[#8b949e]{msg}[/]")
            progress.advance(1)
            self._boot_step += 1

            if self._boot_step >= len(BOOT_SEQUENCE):
                # Boot complete, transition to dashboard
                self.set_timer(0.8, self._go_to_dashboard)

    def _go_to_dashboard(self) -> None:
        """Transition to the main dashboard."""
        self.app.pop_screen()
        from zdb.screens.dashboard import DashboardScreen
        self.app.push_screen(DashboardScreen())

    def action_skip(self) -> None:
        """Skip the intro animation."""
        self._go_to_dashboard()

    def on_key(self, event) -> None:
        """Any key press skips the intro."""
        if event.key != "escape":
            self._go_to_dashboard()

