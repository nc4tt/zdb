"""Main dashboard screen with card-based navigation."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from zdb.backend import CmdStatus, adb_devices


class DashCard(Static, can_focus=True):
    """A focusable navigation card."""

    def __init__(self, icon: str, title: str, desc: str, key: str, screen_name: str, **kwargs):
        super().__init__(**kwargs)
        self._icon = icon
        self._title = title
        self._desc = desc
        self._key = key
        self._screen_name = screen_name

    def compose(self) -> ComposeResult:
        yield Static(self._icon, classes="card-icon")
        yield Static(self._title, classes="card-title")
        yield Static(self._desc, classes="card-desc")
        yield Static(f"Press [{self._key}]", classes="card-key")

    def on_click(self) -> None:
        self._navigate()

    def _navigate(self) -> None:
        if self._screen_name == "adb":
            from zdb.screens.adb_screen import ADBScreen
            self.app.push_screen(ADBScreen())
        elif self._screen_name == "fastboot":
            from zdb.screens.fastboot_screen import FastbootScreen
            self.app.push_screen(FastbootScreen())
        elif self._screen_name == "device":
            from zdb.screens.device_info import DeviceInfoScreen
            self.app.push_screen(DeviceInfoScreen())
        elif self._screen_name == "experimental":
            from zdb.screens.experimental_screen import ExperimentalScreen
            self.app.push_screen(ExperimentalScreen())


class DashboardScreen(Screen):
    """Main navigation dashboard with animated card entrance."""

    BINDINGS = [
        ("1", "go_adb", "ADB"),
        ("2", "go_fastboot", "Fastboot"),
        ("3", "go_device", "Device Info"),
        ("4", "go_experimental", "Experimental"),
        ("x", "go_credits", "Credits"),
        ("c", "go_changelog", "Changelogs"),
        ("r", "refresh_device", "Refresh"),
        ("q", "quit_app", "Quit"),
    ]

    @staticmethod
    def _greeting() -> str:
        """Return a time-based greeting string."""
        hour = datetime.now().hour
        if hour < 12:
            period = "Morning"
        elif hour < 17:
            period = "Afternoon"
        else:
            period = "Evening"
        return f"Good {period}, zdb-er."

    def compose(self) -> ComposeResult:
        with Vertical(id="dashboard-screen"):
            with Container(id="dash-header"):
                yield Static(f"⬡ {self._greeting()}", id="dash-header-title")
                with Horizontal(id="dash-status-row"):
                    yield Static("Checking device status...", id="dash-header-status")
                    yield Button("🔄 Refresh", id="btn-refresh", classes="btn-refresh")

            with Horizontal(id="dash-cards"):
                yield DashCard(
                    icon="📱",
                    title="ADB Operations",
                    desc="Sideload • Reboot • Shell\nPush • Pull • Install",
                    key="1",
                    screen_name="adb",
                    classes="dash-card",
                )
                yield DashCard(
                    icon="⚡",
                    title="Fastboot Mode",
                    desc="Flash • GetVar • Boot\nErase • OEM Unlock",
                    key="2",
                    screen_name="fastboot",
                    classes="dash-card",
                )
                yield DashCard(
                    icon="🔍",
                    title="Device Info",
                    desc="Model • Hardware • SIM\nStorage • Battery • Display",
                    key="3",
                    screen_name="device",
                    classes="dash-card",
                )
                yield DashCard(
                    icon="🧪",
                    title="Experimental",
                    desc="Download ROM • Switch\nTarget Device",
                    key="4",
                    screen_name="experimental",
                    classes="dash-card",
                )

            with Container(id="dash-footer"):
                yield Static(
                    "[bold #4fc3f7]1-4[/] Navigate  [bold #4fc3f7]X[/] Credits  [bold #4fc3f7]C[/] Changelogs  [bold #4fc3f7]R[/] Refresh  [bold #4fc3f7]Q[/] Quit",
                    id="dash-footer-text",
                )
                yield Button("👥 Credits", id="btn-credits", classes="btn-credits")
                yield Button("📋 Changelogs", id="btn-changelog", classes="btn-changelog")
                yield Button("⏻ Exit", id="btn-exit")

    async def on_mount(self) -> None:
        """Animate card entrance and check device status."""
        # Staggered card entrance
        cards = self.query(".dash-card")
        for i, card in enumerate(cards):
            card.styles.opacity = 0.0
        for i, card in enumerate(cards):
            self.set_timer(0.2 * (i + 1), lambda c=card: self._fade_in(c))

        # Check device status
        self._check_device()

    async def on_screen_resume(self) -> None:
        """Refresh greeting and device status when returning to dashboard."""
        self.query_one("#dash-header-title", Static).update(f"⬡ {self._greeting()}")
        self._check_device()

    def _fade_in(self, widget) -> None:
        widget.styles.animate("opacity", value=1.0, duration=0.5)

    def _check_device(self) -> None:
        self.run_worker(self._device_check_worker())

    async def _device_check_worker(self) -> None:
        status_widget = self.query_one("#dash-header-status", Static)
        try:
            result = await adb_devices()
            lines = [l for l in result.stdout.strip().splitlines() if l and not l.startswith("List")]
            if not lines:
                status_widget.update("[#ffa726]⚠ No device connected[/]")
            elif "unauthorized" in lines[0].lower():
                status_widget.update("[#ffa726]🔒 Device connected — Authorization required[/]")
            elif "device" in lines[0].lower():
                serial = lines[0].split()[0]
                status_widget.update(f"[#66bb6a]✓ Device connected: {serial}[/]")
            else:
                status_widget.update("[#8b949e]○ Unknown device state[/]")
        except Exception:
            status_widget.update("[#ef5350]✗ ADB not available[/]")

    def action_go_adb(self) -> None:
        from zdb.screens.adb_screen import ADBScreen
        self.app.push_screen(ADBScreen())

    def action_go_fastboot(self) -> None:
        from zdb.screens.fastboot_screen import FastbootScreen
        self.app.push_screen(FastbootScreen())

    def action_go_device(self) -> None:
        from zdb.screens.device_info import DeviceInfoScreen
        self.app.push_screen(DeviceInfoScreen())

    def action_go_experimental(self) -> None:
        from zdb.screens.experimental_screen import ExperimentalScreen
        self.app.push_screen(ExperimentalScreen())

    def action_go_changelog(self) -> None:
        from zdb.screens.changelog import ChangelogScreen
        self.app.push_screen(ChangelogScreen())

    def action_go_credits(self) -> None:
        from zdb.screens.credits import CreditsScreen
        self.app.push_screen(CreditsScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-exit":
            self.app.exit()
        elif event.button.id == "btn-changelog":
            from zdb.screens.changelog import ChangelogScreen
            self.app.push_screen(ChangelogScreen())
        elif event.button.id == "btn-credits":
            from zdb.screens.credits import CreditsScreen
            self.app.push_screen(CreditsScreen())
        elif event.button.id == "btn-refresh":
            self.action_refresh_device()

    def action_refresh_device(self) -> None:
        """Refresh the device status and greeting."""
        self.query_one("#dash-header-title", Static).update(f"⬡ {self._greeting()}")
        self.query_one("#dash-header-status", Static).update("Checking device status...")
        self._check_device()

    def action_quit_app(self) -> None:
        self.app.exit()
