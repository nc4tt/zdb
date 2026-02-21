"""Changelog screen — version history display."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static


# ── Changelog data ───────────────────────────────────────────────────

CHANGELOGS = [
    (
        "v6.0.0",
        "Credits, Dashboard Buttons & Polish",
        [
            "New Credits screen — acknowledge all contributors",
            "Dashboard footer: Credits, Changelogs, and Exit buttons",
            "Keyboard shortcut [X] to open Credits from dashboard",
            "Updated boot sequence branding to v6",
            "Bumped version to v6",
        ],
    ),
    (
        "v5.0.0",
        "Full ADB & Fastboot Command Coverage",
        [
            "All ADB commands: connect, disconnect, pair, forward, reverse, tcpip, usb",
            "ADB debug: bugreport, install-multiple APKs",
            "ADB root/remount: root, unroot, remount (r/w)",
            "ADB security: disable-verity, enable-verity",
            "ADB server: start-server, kill-server, reconnect",
            "ADB scripting: wait-for-device, get-state, get-serialno, get-devpath",
            "Fastboot flashing: update ZIP, flash all from $OUT",
            "Fastboot erase/format with FS_TYPE and SIZE options",
            "Fastboot slots: set active slot (a/b)",
            "Fastboot logical: create, delete, resize logical partitions",
            "Fastboot bootloader: lock/unlock critical, get_unlock_ability, custom OEM",
            "Fastboot advanced: GSI wipe/disable/status, wipe-super, snapshot-update",
            "Fastboot fetch partition image, stage, get_staged (Android Things)",
            "Dashboard greeting: Good Morning/Afternoon/Evening, zdb-er",
            "Refresh device button (🔄) + R keybinding on dashboard",
            "Auto-refresh device status when returning to dashboard",
            "Bumped version to v5",
        ],
    ),
    (
        "v4.5.2",
        "ROM File Manager",
        [
            "List ROM files in ~/zdb_rom with size and type info",
            "Extract ROM archives (zip, tar, tar.gz, tar.xz, xz, gz, bz2, 7z, rar)",
            "Archive selection dialog for choosing which file to extract",
            "Auto-create ~/zdb_rom directory for ROM storage",
            "Human-readable file sizes in ROM listing",
        ],
    ),
    (
        "v4.5.1",
        "Sudo Password Authentication",
        [
            "Secure password dialog for sudo operations (masked input)",
            "Password piped to sudo -S via stdin (never stored/logged)",
            "Filtered sudo prompts from output for clean display",
            "Incorrect password detection with AUTH_REQUIRED status",
            "Install dependencies now requires authentication",
            "Bumped version to v4.5.1",
        ],
    ),
    (
        "v4.5.0",
        "Install Dependencies & Multi-Distro Support",
        [
            "Auto-detect Linux distribution from /etc/os-release",
            "Install dependencies (adb, fastboot, wget, curl) via package manager",
            "Supports Debian/Ubuntu, RHEL/Fedora, openSUSE, Arch, Alpine, Void, Gentoo, NixOS",
            "Correct package names per distro family (e.g. android-tools vs adb)",
            "Shows detected distro info and exact command before running",
            "Bumped version to v4.5",
        ],
    ),
    (
        "v4.0.0",
        "Experimental Features & Diagnostics",
        [
            "Added Experimental Features tab (4th dashboard card)",
            "ROM download via wget or curl with save directory selection",
            "Device switching — list, select, and set target device",
            "Current target device display (ANDROID_SERIAL)",
            "Real tool version checker (adb, fastboot, wget, curl, python3, java)",
            "Fetches latest platform-tools version from Google SDK repository",
            "Version comparison with color-coded status indicators",
            "Changelogs screen with full version history",
            "Bumped version to v4",
        ],
    ),
    (
        "v3.0.0",
        "Animation Overhaul & ASCII Refresh",
        [
            "Redesigned ASCII logo to slanted 'zdb' text",
            "Glitch-reveal animation on splash screen",
            "Boot sequence progress with status messages",
            "Bumped version to v3",
        ],
    ),
    (
        "v2.0.0",
        "Device Info & Fastboot",
        [
            "Updated ASCII art splash screen",
            "Added comprehensive Device Info screen",
            "Hardware specs: chipset, CPU, RAM, storage",
            "SIM & connectivity info (IMEI, eSIM, operator)",
            "Battery health, temperature, and charging status",
            "Display specs: resolution, DPI, refresh rate",
            "Fastboot operations screen (flash, erase, boot, OEM unlock)",
            "Updated splash screen ASCII art to slanted version",
            "Bumped version to v2",
        ],
    ),
    (
        "v1.0.0",
        "Initial Release",
        [
            "Premium dark TUI with Material Blue accents",
            "Animated splash screen with progress bar",
            "Dashboard with card-based navigation",
            "ADB operations: sideload, reboot, push, pull, install, uninstall",
            "Shell command execution and logcat viewer",
            "Status indicators (running, success, failed, auth required)",
            "Staggered card entrance animations",
            "Async command execution with timeout handling",
            "Device connection status on dashboard",
        ],
    ),
]


# ── Changelog screen ─────────────────────────────────────────────────


class ChangelogScreen(Screen):
    """Scrollable changelog listing all versions."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="op-screen"):
            with Container(classes="op-header"):
                yield Static(
                    "📋 Changelogs  —  [bold #484f58]ESC[/] Back",
                    classes="op-header-title",
                )
                yield Button(
                    "✕ Close",
                    id="btn-close-screen",
                    classes="header-close-btn",
                )

            with Vertical(id="changelog-body"):
                for version, title, changes in CHANGELOGS:
                    with Container(classes="changelog-version"):
                        yield Static(
                            f"[bold #4fc3f7]{version}[/]  —  [bold #e6edf3]{title}[/]",
                            classes="changelog-version-title",
                        )
                        change_lines = "\n".join(
                            f"  [#66bb6a]•[/]  {c}" for c in changes
                        )
                        yield Static(change_lines, classes="changelog-items")

    async def on_mount(self) -> None:
        """Fade in version blocks."""
        blocks = self.query(".changelog-version")
        for block in blocks:
            block.styles.opacity = 0.0
        for i, block in enumerate(blocks):
            self.set_timer(0.15 * (i + 1), lambda w=block: self._fade_in(w))

    def _fade_in(self, widget) -> None:
        widget.styles.animate("opacity", value=1.0, duration=0.4)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-screen":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
