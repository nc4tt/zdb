"""Device information screen with comprehensive hardware/software details."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, Center
from textual.screen import Screen
from textual.widgets import Static, Button

from zdb.backend import CmdStatus, DeviceInfo, get_device_info
from zdb.widgets.ascii_art import DEVICE_ART


class InfoRow(Static):
    """A key-value row in the device info panel."""

    def __init__(self, label: str, value: str, **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._value = value

    def compose(self) -> ComposeResult:
        with Horizontal(classes="info-row"):
            yield Static(self._label, classes="info-label")
            yield Static(self._value, classes="info-value")


class InfoSection(Static):
    """A grouped section of device info."""

    def __init__(self, title: str, rows: list[tuple[str, str]], **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._rows = rows

    def compose(self) -> ComposeResult:
        with Vertical(classes="info-section"):
            yield Static(self._title, classes="info-section-title")
            for label, value in self._rows:
                if value:  # Only show non-empty values
                    yield InfoRow(label, value)


class DeviceInfoScreen(Screen):
    """Comprehensive device information dashboard."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="device-info-screen"):
            with Container(id="di-header"):
                yield Static(
                    "🔍 Device Information  —  [bold #484f58]ESC[/] Back  [bold #484f58]R[/] Refresh",
                    id="di-header-title",
                )
                yield Button("✕ Close", id="btn-close-screen", classes="header-close-btn")

            with Horizontal(id="di-body"):
                with Vertical(id="di-device-panel"):
                    yield Static(DEVICE_ART, id="di-device-art")
                    yield Static("Loading...", id="di-device-name")
                    yield Static("", id="di-device-brand")

                with Vertical(id="di-info-panel"):
                    yield Static(
                        "[#4fc3f7]Scanning device...[/]",
                        id="di-loading",
                    )

            with Container(id="di-footer"):
                yield Static(
                    "[bold #4fc3f7]R[/] Refresh  [bold #4fc3f7]ESC[/] Back",
                    id="di-footer-text",
                )

    async def on_mount(self) -> None:
        self.run_worker(self._load_device_info())

    def action_refresh(self) -> None:
        self.run_worker(self._load_device_info())

    async def _load_device_info(self) -> None:
        """Load and display device information."""
        loading = self.query_one("#di-loading", Static)
        loading.update("[#4fc3f7]⟳ Scanning device...[/]")

        try:
            info = await get_device_info()
        except Exception as e:
            loading.update(f"[#ef5350]✗ Error: {e}[/]")
            return

        if info is None:
            name_widget = self.query_one("#di-device-name", Static)
            brand_widget = self.query_one("#di-device-brand", Static)
            name_widget.update("[#484f58]No Device")
            brand_widget.update("")
            loading.update(
                "[#ffa726]⚠ No device connected\n\n"
                "[#8b949e]Connect an Android device via USB and\n"
                "enable USB debugging in Developer Options.\n\n"
                "Press [bold]R[/] to refresh.[/]"
            )
            return

        # Check if unauthorized
        if info.auth_status == "⚠ Unauthorized":
            name_widget = self.query_one("#di-device-name", Static)
            brand_widget = self.query_one("#di-device-brand", Static)
            name_widget.update(f"[#ffa726]{info.serial}")
            brand_widget.update("[#ffa726]Authorization Required")
            loading.update(
                "[#ffa726]🔒 Device requires authorization\n\n"
                "[#8b949e]Check your device screen and\n"
                "tap 'Allow USB Debugging'.\n\n"
                "Press [bold]R[/] to refresh.[/]"
            )
            return

        # Update device panel
        name_widget = self.query_one("#di-device-name", Static)
        brand_widget = self.query_one("#di-device-brand", Static)
        name_widget.update(f"[bold #e6edf3]{info.model}[/]")
        brand_widget.update(f"[#8b949e]{info.brand} • {info.codename}[/]")

        # Build info sections
        info_panel = self.query_one("#di-info-panel", Vertical)
        loading.remove()

        sections = self._build_sections(info)

        for i, section in enumerate(sections):
            section.styles.opacity = 0.0
            info_panel.mount(section)
            self.set_timer(0.1 * (i + 1), lambda s=section: self._fade_in(s))

    def _fade_in(self, widget) -> None:
        widget.styles.animate("opacity", value=1.0, duration=0.4)

    def _build_sections(self, info: DeviceInfo) -> list[InfoSection]:
        """Build all info sections from device data."""
        sections = []

        # Identity
        sections.append(InfoSection("📱 Identity", [
            ("Model", info.model),
            ("Manufacturer", info.manufacturer),
            ("Brand", info.brand),
            ("Codename", info.codename),
            ("Serial", info.serial),
        ]))

        # Hardware
        hw_rows = [
            ("Chipset", info.chipset),
            ("SoC / Platform", info.soc),
            ("CPU Architecture", info.cpu_arch),
        ]
        if info.cpu_cores:
            hw_rows.append(("CPU Cores", info.cpu_cores))
        if info.cpu_freq:
            hw_rows.append(("Max CPU Freq", info.cpu_freq))
        sections.append(InfoSection("🔧 Hardware", hw_rows))

        # Memory
        mem_rows = [("Total RAM", info.ram_total)]
        if info.ram_available:
            mem_rows.append(("Available RAM", info.ram_available))
            # Calculate usage bar
            try:
                total = float(info.ram_total.replace(" GB", ""))
                avail = float(info.ram_available.replace(" GB", ""))
                used_pct = ((total - avail) / total) * 100
                bar_len = 20
                filled = int(bar_len * used_pct / 100)
                bar = "█" * filled + "░" * (bar_len - filled)
                mem_rows.append(("Usage", f"{bar} {used_pct:.0f}%"))
            except (ValueError, ZeroDivisionError):
                pass
        sections.append(InfoSection("💾 Memory", mem_rows))

        # Storage
        stor_rows = []
        if info.storage_total:
            stor_rows.append(("Total", info.storage_total))
        if info.storage_used:
            stor_rows.append(("Used", info.storage_used))
        if info.storage_free:
            stor_rows.append(("Free", info.storage_free))
            try:
                # Try to build usage bar from df output
                total_str = info.storage_total.upper()
                used_str = info.storage_used.upper()
                # Simple percentage from df columns
                if info.storage_total and info.storage_used:
                    bar_len = 20
                    # Try extracting numeric values
                    t_val = float(''.join(c for c in info.storage_total if c.isdigit() or c == '.'))
                    u_val = float(''.join(c for c in info.storage_used if c.isdigit() or c == '.'))
                    if t_val > 0:
                        pct = (u_val / t_val) * 100
                        filled = int(bar_len * pct / 100)
                        bar = "█" * filled + "░" * (bar_len - filled)
                        stor_rows.append(("Usage", f"{bar} {pct:.0f}%"))
            except (ValueError, ZeroDivisionError):
                pass
        if stor_rows:
            sections.append(InfoSection("📀 Storage", stor_rows))

        # Display
        disp_rows = []
        if info.screen_resolution:
            disp_rows.append(("Resolution", info.screen_resolution))
        if info.screen_dpi:
            disp_rows.append(("DPI", info.screen_dpi))
        if info.screen_refresh_rate:
            disp_rows.append(("Refresh Rate", info.screen_refresh_rate))
        if disp_rows:
            sections.append(InfoSection("🖥  Display", disp_rows))

        # Network / SIM
        net_rows = []
        if info.imei:
            net_rows.append(("IMEI", info.imei))
        if info.sim_slots:
            net_rows.append(("SIM Status", info.sim_slots))
        if info.sim_provider:
            net_rows.append(("SIM Provider", info.sim_provider))
        if info.sim_operator:
            net_rows.append(("Operator", info.sim_operator))
        if info.esim_support:
            net_rows.append(("eSIM", info.esim_support))
        if net_rows:
            sections.append(InfoSection("📡 Network / SIM", net_rows))

        # Software
        sections.append(InfoSection("📦 Software", [
            ("Android", info.android_version),
            ("SDK Level", info.sdk_level),
            ("Security Patch", info.security_patch),
            ("Build Number", info.build_number),
            ("Kernel", info.kernel_version),
        ]))

        # Battery
        bat_rows = []
        if info.battery_level:
            # Battery bar
            try:
                pct = int(info.battery_level.replace("%", ""))
                bar_len = 20
                filled = int(bar_len * pct / 100)
                if pct > 60:
                    color = "#66bb6a"
                elif pct > 20:
                    color = "#ffa726"
                else:
                    color = "#ef5350"
                bar = "█" * filled + "░" * (bar_len - filled)
                bat_rows.append(("Level", f"{bar} {info.battery_level}"))
            except ValueError:
                bat_rows.append(("Level", info.battery_level))
        if info.battery_health:
            bat_rows.append(("Health", info.battery_health))
        if info.battery_temp:
            bat_rows.append(("Temperature", info.battery_temp))
        if info.charging_status:
            bat_rows.append(("Status", info.charging_status))
        if bat_rows:
            sections.append(InfoSection("🔋 Battery", bat_rows))

        # Connection
        sections.append(InfoSection("🔌 Connection", [
            ("Type", info.connection_type),
            ("Authorization", info.auth_status),
        ]))

        return sections

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-screen":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
