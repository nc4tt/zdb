"""Experimental features screen — ROM download & device switching."""

from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from zdb.backend import (
    CmdStatus,
    ConnectedDevice,
    RomFileInfo,
    check_tool_versions,
    check_zdb_update,
    detect_distro,
    download_file,
    extract_rom,
    get_connected_devices,
    get_install_command,
    get_rom_dir,
    get_target_device,
    install_dependencies,
    list_rom_files,
    run_cmd_sudo,
    set_target_device,
)
from zdb.widgets.command_output import CommandOutput
from zdb.widgets.status_bar import StatusIndicator


# ── Reusable dialogs ─────────────────────────────────────────────────


class _InputDialog(Screen):
    """Modal dialog for text input (local copy to avoid circular import)."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        title: str,
        placeholder: str,
        callback,
        fields: list[tuple[str, str]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._title = title
        self._placeholder = placeholder
        self._callback = callback
        self._fields = fields or [(placeholder, "input_0")]

    def compose(self) -> ComposeResult:
        with Container(classes="input-dialog"):
            with Vertical(classes="input-dialog-box"):
                yield Static(self._title, classes="input-dialog-title")
                for placeholder, field_id in self._fields:
                    yield Input(
                        placeholder=placeholder, id=field_id, classes="input-field"
                    )
                with Horizontal(classes="dialog-buttons"):
                    yield Button(
                        "Execute",
                        id="btn-execute",
                        classes="dialog-btn btn-primary",
                    )
                    yield Button(
                        "Cancel",
                        id="btn-cancel",
                        classes="dialog-btn btn-secondary",
                    )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-execute":
            values = [
                self.query_one(f"#{fid}", Input).value for _, fid in self._fields
            ]
            self.app.pop_screen()
            self._callback(*values)
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        values = [
            self.query_one(f"#{fid}", Input).value for _, fid in self._fields
        ]
        self.app.pop_screen()
        self._callback(*values)

    def action_cancel(self) -> None:
        self.app.pop_screen()


class _PasswordDialog(Screen):
    """Modal dialog for secure password input (sudo authentication)."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, message: str, callback, **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._message = message
        self._callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="input-dialog"):
            with Vertical(classes="input-dialog-box"):
                yield Static(self._title, classes="input-dialog-title")
                yield Static(
                    f"[#8b949e]{self._message}[/]",
                    classes="password-info",
                )
                yield Input(
                    placeholder="Password...",
                    id="pw_input",
                    password=True,
                    classes="input-field",
                )
                with Horizontal(classes="dialog-buttons"):
                    yield Button(
                        "🔓 Authenticate",
                        id="btn-pw-ok",
                        classes="dialog-btn btn-primary",
                    )
                    yield Button(
                        "Cancel",
                        id="btn-pw-cancel",
                        classes="dialog-btn btn-secondary",
                    )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pw-ok":
            pw = self.query_one("#pw_input", Input).value
            self.app.pop_screen()
            self._callback(pw)
        elif event.button.id == "btn-pw-cancel":
            self.app.pop_screen()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        pw = self.query_one("#pw_input", Input).value
        self.app.pop_screen()
        self._callback(pw)

    def action_cancel(self) -> None:
        self.app.pop_screen()


# ── Device selection dialog ──────────────────────────────────────────


class DeviceItem(Static, can_focus=True):
    """A clickable device entry."""

    def __init__(self, device: ConnectedDevice, callback, **kwargs):
        label = f"  {device.serial}  —  {device.model or '?'}  [{device.status}]"
        super().__init__(label, **kwargs)
        self._device = device
        self._callback = callback

    def on_click(self) -> None:
        self._callback(self._device.serial)


class DeviceSelectDialog(Screen):
    """Modal that lists connected devices for selection."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, devices: list[ConnectedDevice], callback, **kwargs):
        super().__init__(**kwargs)
        self._devices = devices
        self._callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="input-dialog"):
            with Vertical(classes="input-dialog-box device-select-box"):
                yield Static(
                    "🔀  Select Target Device",
                    classes="input-dialog-title",
                )
                if not self._devices:
                    yield Static(
                        "[#8b949e]No devices connected[/]",
                        classes="device-empty",
                    )
                else:
                    for dev in self._devices:
                        yield DeviceItem(
                            dev,
                            self._on_select,
                            classes="device-select-item",
                        )
                with Horizontal(classes="dialog-buttons"):
                    yield Button(
                        "Cancel",
                        id="btn-cancel-dev",
                        classes="dialog-btn btn-secondary",
                    )

    def _on_select(self, serial: str) -> None:
        self.app.pop_screen()
        self._callback(serial)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-dev":
            self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


# ── ROM archive selection dialog ─────────────────────────────────────


class _RomArchiveItem(Static, can_focus=True):
    """A clickable ROM archive entry."""

    def __init__(self, rom: RomFileInfo, callback, **kwargs):
        label = f"  📦  {rom.name}  —  {rom.size_human}  [{rom.archive_type}]"
        super().__init__(label, **kwargs)
        self._rom = rom
        self._callback = callback

    def on_click(self) -> None:
        self._callback(self._rom.path)


class _RomSelectDialog(Screen):
    """Modal that lists ROM archives for extraction."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, archives: list[RomFileInfo], callback, **kwargs):
        super().__init__(**kwargs)
        self._archives = archives
        self._callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="input-dialog"):
            with Vertical(classes="input-dialog-box device-select-box"):
                yield Static(
                    "📤  Select Archive to Extract",
                    classes="input-dialog-title",
                )
                for rom in self._archives:
                    yield _RomArchiveItem(
                        rom,
                        self._on_select,
                        classes="device-select-item",
                    )
                with Horizontal(classes="dialog-buttons"):
                    yield Button(
                        "Cancel",
                        id="btn-cancel-rom",
                        classes="dialog-btn btn-secondary",
                    )

    def _on_select(self, path: str) -> None:
        self.app.pop_screen()
        self._callback(path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-rom":
            self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


# ── Sidebar menu items ───────────────────────────────────────────────

EXPERIMENTAL_COMMANDS = [
    ("─── Download ───", None),
    ("  🌐  Download ROM (wget)", "dl_wget"),
    ("  🌐  Download ROM (curl)", "dl_curl"),
    ("─── ROM Manager ───", None),
    ("  📂  List ROM Files", "list_roms"),
    ("  📤  Extract ROM Archive", "extract_rom"),
    ("─── Device ───", None),
    ("  📱  List Connected Devices", "list_devices"),
    ("  🔀  Switch Target Device", "switch_device"),
    ("  📋  Current Target", "show_target"),
    ("─── Diagnostics ───", None),
    ("  🔧  Check Tools Up-to-Date", "check_tools"),
    ("  🔄  Check for zdb Updates", "check_zdb_update"),
    ("  📦  Install Dependencies", "install_deps"),
]


class ExpMenuItem(Static, can_focus=True):
    """A focusable sidebar item."""

    def __init__(self, label: str, cmd_key: str | None, **kwargs):
        super().__init__(label, **kwargs)
        self._cmd_key = cmd_key

    def on_click(self) -> None:
        if self._cmd_key:
            self.screen._execute_command(self._cmd_key)


# ── Main screen ──────────────────────────────────────────────────────


class ExperimentalScreen(Screen):
    """Experimental Features screen with download & device switching."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="op-screen"):
            with Container(classes="op-header"):
                yield Static(
                    "🧪 Experimental Features  —  [bold #484f58]ESC[/] Back",
                    classes="op-header-title",
                )
                yield Button(
                    "✕ Close",
                    id="btn-close-screen",
                    classes="header-close-btn",
                )

            with Horizontal(classes="op-body"):
                with Vertical(classes="op-sidebar"):
                    for label, cmd_key in EXPERIMENTAL_COMMANDS:
                        if cmd_key is None:
                            yield Static(label, classes="op-category-label")
                        else:
                            yield ExpMenuItem(
                                label, cmd_key, classes="op-list-item"
                            )

                with Vertical(classes="op-content"):
                    yield StatusIndicator(id="exp-status")
                    yield CommandOutput(id="exp-output")

    async def on_mount(self) -> None:
        items = self.query(".op-list-item")
        for item in items:
            item.styles.opacity = 0.0
        for i, item in enumerate(items):
            self.set_timer(0.05 * (i + 1), lambda w=item: self._fade_in(w))

    def _fade_in(self, widget) -> None:
        widget.styles.animate("opacity", value=1.0, duration=0.3)

    # ── Command routing ──────────────────────────────────────────

    def _execute_command(self, cmd_key: str) -> None:
        if cmd_key == "dl_wget":
            self.app.push_screen(
                _InputDialog(
                    "Download ROM (wget)",
                    "URL to download...",
                    self._do_download_wget,
                    fields=[
                        ("ROM URL (https://...)...", "input_url"),
                        ("Save directory (default: .)...", "input_dir"),
                    ],
                )
            )
        elif cmd_key == "dl_curl":
            self.app.push_screen(
                _InputDialog(
                    "Download ROM (curl)",
                    "URL to download...",
                    self._do_download_curl,
                    fields=[
                        ("ROM URL (https://...)...", "input_url"),
                        ("Save directory (default: .)...", "input_dir"),
                    ],
                )
            )
        elif cmd_key == "list_devices":
            self.run_worker(self._run_list_devices())
        elif cmd_key == "switch_device":
            self.run_worker(self._open_device_selector())
        elif cmd_key == "show_target":
            self._show_current_target()
        elif cmd_key == "check_tools":
            self.run_worker(self._run_check_tools())
        elif cmd_key == "check_zdb_update":
            self.run_worker(self._run_check_zdb_update())
        elif cmd_key == "install_deps":
            self.run_worker(self._run_install_deps())
        elif cmd_key == "list_roms":
            self._show_rom_list()
        elif cmd_key == "extract_rom":
            self._show_extract_dialog()

    # ── Helpers ───────────────────────────────────────────────────

    def _set_status(self, status: CmdStatus) -> None:
        self.query_one("#exp-status", StatusIndicator).status = status

    def _get_output(self) -> CommandOutput:
        return self.query_one("#exp-output", CommandOutput)

    # ── Download ─────────────────────────────────────────────────

    def _do_download_wget(self, url: str, save_dir: str) -> None:
        if url.strip():
            self.run_worker(
                self._run_download(url.strip(), save_dir.strip() or ".", False)
            )

    def _do_download_curl(self, url: str, save_dir: str) -> None:
        if url.strip():
            self.run_worker(
                self._run_download(url.strip(), save_dir.strip() or ".", True)
            )

    async def _run_download(
        self, url: str, save_dir: str, use_curl: bool
    ) -> None:
        output = self._get_output()
        tool = "curl" if use_curl else "wget"
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"{tool}: {url} → {save_dir}")

        result = await download_file(url, save_dir, use_curl=use_curl)

        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        status_text = (
            "Download complete ✓"
            if result.status == CmdStatus.SUCCESS
            else "Download failed ✗"
        )
        output.log_status(status_text, result.status)
        self._set_status(result.status)

    # ── Device listing ───────────────────────────────────────────

    async def _run_list_devices(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("adb devices -l")

        devices = await get_connected_devices()

        if not devices:
            output.log_output("No devices connected.", CmdStatus.FAILED)
            self._set_status(CmdStatus.FAILED)
            return

        lines = []
        current = get_target_device()
        for d in devices:
            marker = " ◀ active" if d.serial == current else ""
            lines.append(
                f"  {d.serial}  │  {d.model or '—':16s}  │  {d.status}{marker}"
            )
        header = f"  {'Serial':20s}  │  {'Model':16s}  │  Status"
        separator = "  " + "─" * 60
        output.log_output(
            header + "\n" + separator + "\n" + "\n".join(lines),
            CmdStatus.SUCCESS,
        )
        output.log_status(f"Found {len(devices)} device(s)", CmdStatus.SUCCESS)
        self._set_status(CmdStatus.SUCCESS)

    # ── Device switching ─────────────────────────────────────────

    async def _open_device_selector(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("Scanning connected devices...")

        devices = await get_connected_devices()

        if len(devices) < 2:
            msg = (
                "Need ≥2 connected devices to switch target.\n"
                f"Currently found: {len(devices)} device(s)."
            )
            output.log_output(msg, CmdStatus.FAILED)
            self._set_status(CmdStatus.FAILED)
            return

        self._set_status(CmdStatus.IDLE)
        self.app.push_screen(
            DeviceSelectDialog(devices, self._on_device_selected)
        )

    def _on_device_selected(self, serial: str) -> None:
        set_target_device(serial)
        output = self._get_output()
        output.log_command(f"set ANDROID_SERIAL={serial}")
        output.log_output(
            f"Target device set to: [bold #4fc3f7]{serial}[/]",
            CmdStatus.SUCCESS,
        )
        output.log_status("Device switched ✓", CmdStatus.SUCCESS)
        self._set_status(CmdStatus.SUCCESS)

    def _show_current_target(self) -> None:
        output = self._get_output()
        target = get_target_device()
        if target:
            output.log_command("echo $ANDROID_SERIAL")
            output.log_output(
                f"Current target: [bold #4fc3f7]{target}[/]",
                CmdStatus.SUCCESS,
            )
            self._set_status(CmdStatus.SUCCESS)
        else:
            output.log_command("echo $ANDROID_SERIAL")
            output.log_output(
                "No target device set — using default (first connected).",
                CmdStatus.IDLE,
            )
            self._set_status(CmdStatus.IDLE)

    # ── Tool version check ───────────────────────────────────────

    async def _run_check_tools(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("Checking tool versions (adb, fastboot, wget, curl, python3, java)...")

        infos = await check_tool_versions()

        lines = []
        all_ok = True
        for t in infos:
            if not t.is_installed:
                icon = "[#ef5350]✗[/]"
                ver_text = "[#ef5350]not installed[/]"
                all_ok = False
            elif t.is_uptodate is True:
                icon = "[#66bb6a]✓[/]"
                ver_text = f"[#66bb6a]{t.installed_version}[/]"
            elif t.is_uptodate is False:
                icon = "[#ffa726]⬆[/]"
                ver_text = f"[#ffa726]{t.installed_version}[/]"
                all_ok = False
            else:
                icon = "[#4fc3f7]●[/]"
                ver_text = f"[#4fc3f7]{t.installed_version}[/]"

            latest_col = ""
            if t.latest_version:
                latest_col = f"  →  latest: [bold]{t.latest_version}[/]"

            path_col = ""
            if t.path:
                path_col = f"  [#484f58]({t.path})[/]"

            lines.append(f"  {icon}  {t.name:12s}  {ver_text}{latest_col}{path_col}")

        header = "  ─── Tool Version Report ───"
        output.log_output(
            header + "\n\n" + "\n".join(lines),
            CmdStatus.SUCCESS if all_ok else CmdStatus.IDLE,
        )

        if all_ok:
            output.log_status("All tools up-to-date ✓", CmdStatus.SUCCESS)
            self._set_status(CmdStatus.SUCCESS)
        else:
            output.log_status(
                "Some tools missing or outdated — see report above",
                CmdStatus.IDLE,
            )
            self._set_status(CmdStatus.IDLE)


    async def _run_check_zdb_update(self) -> None:
        from zdb import __version__
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("Checking latest zdb update via API...")

        info = await check_zdb_update(__version__)

        if info.error:
            output.log_output(f"[#ef5350]✗ {info.error}[/]", CmdStatus.FAILED)
            self._set_status(CmdStatus.FAILED)
            return

        if not info.is_newer:
            output.log_output(
                f"[#66bb6a]✓[/] You are running the latest version: [bold #4fc3f7]v{__version__}[/]\n"
                f"  No updates available from the API (latest known is v{info.latest_version}).",
                CmdStatus.SUCCESS,
            )
            output.log_status("zdb is up-to-date ✓", CmdStatus.SUCCESS)
            self._set_status(CmdStatus.SUCCESS)
        else:
            msg = (
                f"  [#ffa726]⬆ Update Available![/]\n\n"
                f"  Current Version:  [#8b949e]v{__version__}[/]\n"
                f"  Latest Version:   [bold #4fc3f7]v{info.latest_version}[/]\n\n"
                f"  [bold #e6edf3]Changelog:[/\n{info.changelog}\n\n"
                f"  [bold #e6edf3]Download:[/]      [underline #58a6ff]{info.download_url}[/]"
            )
            output.log_output(msg, CmdStatus.IDLE)
            output.log_status(f"v{info.latest_version} available", CmdStatus.IDLE)
            self._set_status(CmdStatus.IDLE)


    # ── Install dependencies ─────────────────────────────────────

    async def _run_install_deps(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("Detecting distribution...")

        distro = detect_distro()

        if not distro.pkg_manager:
            output.log_output(
                "[#ef5350]✗ Could not detect package manager.[/]\n"
                "Please install adb, fastboot, wget, curl manually.",
                CmdStatus.FAILED,
            )
            self._set_status(CmdStatus.FAILED)
            return

        packages = ["adb", "fastboot", "wget", "curl"]
        _, human_cmd = get_install_command(distro, packages)

        output.log_output(
            f"  [#4fc3f7]Distro:[/]     {distro.name}\n"
            f"  [#4fc3f7]Family:[/]     {distro.family}\n"
            f"  [#4fc3f7]Pkg Mgr:[/]    {distro.pkg_manager}\n"
            f"\n  [bold #e6edf3]Command:[/]  [#ffa726]{human_cmd}[/]\n"
            f"\n  [#8b949e]Waiting for authentication...[/]",
            CmdStatus.RUNNING,
        )
        self._set_status(CmdStatus.AUTH_REQUIRED)

        # Show password dialog
        self.app.push_screen(
            _PasswordDialog(
                "🔐  Sudo Authentication",
                f"Enter password to run:\n{human_cmd}",
                lambda pw: self._do_install_with_password(pw, packages),
            )
        )

    def _do_install_with_password(self, password: str, packages: list[str]) -> None:
        if password.strip():
            self.run_worker(self._exec_install(password.strip(), packages))
        else:
            output = self._get_output()
            output.log_output("[#ef5350]No password provided.[/]", CmdStatus.FAILED)
            self._set_status(CmdStatus.FAILED)

    async def _exec_install(self, password: str, packages: list[str]) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_output("  [#8b949e]Authenticating and installing...[/]", CmdStatus.RUNNING)

        _, result = await install_dependencies(packages, password=password)

        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)

        if result.status == CmdStatus.SUCCESS:
            output.log_status("Dependencies installed successfully ✓", CmdStatus.SUCCESS)
            self._set_status(CmdStatus.SUCCESS)
        elif result.status == CmdStatus.AUTH_REQUIRED:
            output.log_status("Authentication failed — incorrect password", CmdStatus.AUTH_REQUIRED)
            self._set_status(CmdStatus.AUTH_REQUIRED)
        else:
            output.log_status(
                "Install failed — check output above",
                CmdStatus.FAILED,
            )
            self._set_status(CmdStatus.FAILED)

    # ── ROM management ───────────────────────────────────────────

    def _show_rom_list(self) -> None:
        output = self._get_output()
        rom_dir = get_rom_dir()
        output.log_command(f"ls {rom_dir}")

        files = list_rom_files()

        if not files:
            output.log_output(
                f"[#8b949e]No files in[/] [bold]{rom_dir}[/]\n"
                "[#8b949e]Download ROM files first or place them in the directory.[/]",
                CmdStatus.IDLE,
            )
            self._set_status(CmdStatus.IDLE)
            return

        lines = []
        total_size = 0
        for f in files:
            total_size += f.size_bytes
            icon = "📦" if f.archive_type != "unknown" else "📄"
            atype = f"[#4fc3f7]{f.archive_type}[/]" if f.archive_type != "unknown" else "[#484f58]—[/]"
            lines.append(f"  {icon}  {f.name:40s}  {f.size_human:>10s}  {atype}")

        from zdb.backend import _human_size
        header = f"  [bold #e6edf3]Directory:[/] {rom_dir}"
        separator = "  " + "─" * 65
        footer = f"\n  [bold]{len(files)}[/] file(s), total: [bold]{_human_size(total_size)}[/]"

        output.log_output(
            header + "\n" + separator + "\n" + "\n".join(lines) + "\n" + separator + footer,
            CmdStatus.SUCCESS,
        )
        output.log_status(f"Listed {len(files)} ROM file(s)", CmdStatus.SUCCESS)
        self._set_status(CmdStatus.SUCCESS)

    def _show_extract_dialog(self) -> None:
        files = list_rom_files()
        archives = [f for f in files if f.archive_type != "unknown"]

        if not archives:
            output = self._get_output()
            rom_dir = get_rom_dir()
            output.log_command("Extract ROM Archive")
            output.log_output(
                f"[#ef5350]No extractable archives found in[/] [bold]{rom_dir}[/]\n"
                "[#8b949e]Supported: .zip, .tar, .tar.gz, .tar.xz, .xz, .gz, .bz2, .7z, .rar[/]",
                CmdStatus.FAILED,
            )
            self._set_status(CmdStatus.FAILED)
            return

        if len(archives) == 1:
            # Only one archive — extract directly without showing dialog
            self._on_rom_selected(archives[0].path)
            return

        # Multiple archives — show selection dialog
        self.app.push_screen(
            _RomSelectDialog(archives, self._on_rom_selected)
        )

    def _on_rom_selected(self, file_path: str) -> None:
        self.run_worker(self._run_extract_rom(file_path))

    async def _run_extract_rom(self, file_path: str) -> None:
        output = self._get_output()
        rom_dir = get_rom_dir()
        basename = os.path.basename(file_path)
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"Extracting {basename} → {rom_dir}")

        result = await extract_rom(file_path, rom_dir)

        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)

        if result.status == CmdStatus.SUCCESS:
            output.log_status(f"Extracted {basename} ✓", CmdStatus.SUCCESS)
            self._set_status(CmdStatus.SUCCESS)
        else:
            output.log_status(f"Extraction failed: {basename}", CmdStatus.FAILED)
            self._set_status(CmdStatus.FAILED)

    # ── Navigation ───────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-screen":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
