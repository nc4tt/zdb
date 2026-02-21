"""ADB operations screen with command sidebar and output panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from zdb.backend import (
    CmdStatus,
    adb_bugreport,
    adb_connect,
    adb_devices,
    adb_disable_verity,
    adb_disconnect,
    adb_enable_verity,
    adb_forward,
    adb_forward_list,
    adb_get_devpath,
    adb_get_serialno,
    adb_get_state,
    adb_install,
    adb_install_multiple,
    adb_kill_server,
    adb_logcat,
    adb_pair,
    adb_pull,
    adb_push,
    adb_reboot,
    adb_reconnect,
    adb_remount,
    adb_reverse,
    adb_reverse_list,
    adb_root,
    adb_shell,
    adb_sideload,
    adb_start_server,
    adb_tcpip,
    adb_uninstall,
    adb_unroot,
    adb_usb,
    adb_wait_for_device,
)
from zdb.widgets.command_output import CommandOutput
from zdb.widgets.status_bar import StatusIndicator


class InputDialog(Screen):
    """Modal dialog for text input."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, placeholder: str, callback, fields: list[tuple[str, str]] | None = None, **kwargs):
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
                    yield Input(placeholder=placeholder, id=field_id, classes="input-field")
                with Horizontal(classes="dialog-buttons"):
                    yield Button("Execute", id="btn-execute", classes="dialog-btn btn-primary")
                    yield Button("Cancel", id="btn-cancel", classes="dialog-btn btn-secondary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-execute":
            values = []
            for _, field_id in self._fields:
                inp = self.query_one(f"#{field_id}", Input)
                values.append(inp.value)
            self.app.pop_screen()
            self._callback(*values)
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter key submits."""
        values = []
        for _, field_id in self._fields:
            inp = self.query_one(f"#{field_id}", Input)
            values.append(inp.value)
        self.app.pop_screen()
        self._callback(*values)

    def action_cancel(self) -> None:
        self.app.pop_screen()


class ConfirmDialog(Screen):
    """Modal confirmation dialog for dangerous operations."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, message: str, callback, **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._message = message
        self._callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="input-dialog"):
            with Vertical(id="confirm-box"):
                yield Static(self._title, id="confirm-title")
                yield Static(self._message, id="confirm-message")
                with Horizontal(classes="dialog-buttons"):
                    yield Button("Confirm", id="btn-confirm", classes="dialog-btn btn-danger")
                    yield Button("Cancel", id="btn-cancel-confirm", classes="dialog-btn btn-secondary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.app.pop_screen()
            self._callback()
        else:
            self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


ADB_COMMANDS = [
    ("─── Device ───", None),
    ("  📋  List Devices", "devices"),
    ("─── Sideload ───", None),
    ("  📦  Sideload ZIP", "sideload"),
    ("─── Reboot ───", None),
    ("  🔄  Reboot → System", "reboot_system"),
    ("  🔄  Reboot → Recovery", "reboot_recovery"),
    ("  🔄  Reboot → Bootloader", "reboot_bootloader"),
    ("  🔄  Reboot → Fastboot", "reboot_fastboot"),
    ("  🔄  Reboot → Sideload", "reboot_sideload"),
    ("─── File Transfer ───", None),
    ("  📤  Push File", "push"),
    ("  📥  Pull File", "pull"),
    ("─── Apps ───", None),
    ("  📲  Install APK", "install"),
    ("  📲  Install Multiple APKs", "install_multiple"),
    ("  🗑   Uninstall Package", "uninstall"),
    ("─── Debug ───", None),
    ("  📝  Logcat", "logcat"),
    ("  💻  Shell Command", "shell"),
    ("  🐛  Bugreport", "bugreport"),
    ("─── Networking ───", None),
    ("  🌐  Connect (TCP/IP)", "connect"),
    ("  🔌  Disconnect", "disconnect"),
    ("  🔗  Pair Device", "pair"),
    ("  📡  TCP/IP Mode", "tcpip"),
    ("  🔌  USB Mode", "usb"),
    ("  ➡️   Forward Port", "forward"),
    ("  📋  Forward List", "forward_list"),
    ("  ⬅️   Reverse Port", "reverse"),
    ("  📋  Reverse List", "reverse_list"),
    ("─── Root / Remount ───", None),
    ("  🔓  Root (adbd)", "root"),
    ("  🔒  Unroot (adbd)", "unroot"),
    ("  💾  Remount (r/w)", "remount"),
    ("─── Security ───", None),
    ("  🛡   Disable Verity", "disable_verity"),
    ("  🛡   Enable Verity", "enable_verity"),
    ("─── Server ───", None),
    ("  ▶️   Start Server", "start_server"),
    ("  ⏹   Kill Server", "kill_server"),
    ("  🔄  Reconnect", "reconnect"),
    ("─── Scripting ───", None),
    ("  ⏳  Wait for Device", "wait_for_device"),
    ("  📊  Get State", "get_state"),
    ("  🔢  Get Serial No", "get_serialno"),
    ("  📁  Get Dev Path", "get_devpath"),
]


class ADBMenuItem(Static, can_focus=True):
    """A focusable menu item in the ADB sidebar."""

    def __init__(self, label: str, cmd_key: str | None, **kwargs):
        super().__init__(label, **kwargs)
        self._cmd_key = cmd_key

    def on_click(self) -> None:
        if self._cmd_key:
            self.screen._execute_command(self._cmd_key)


class ADBScreen(Screen):
    """ADB operations screen with sidebar navigation and output panel."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="op-screen"):
            with Container(classes="op-header"):
                yield Static(
                    "📱 ADB Operations  —  [bold #484f58]ESC[/] Back",
                    classes="op-header-title",
                )
                yield Button("✕ Close", id="btn-close-screen", classes="header-close-btn")

            with Horizontal(classes="op-body"):
                with Vertical(classes="op-sidebar"):
                    for label, cmd_key in ADB_COMMANDS:
                        if cmd_key is None:
                            yield Static(label, classes="op-category-label")
                        else:
                            yield ADBMenuItem(label, cmd_key, classes="op-list-item")

                with Vertical(classes="op-content"):
                    yield StatusIndicator(id="adb-status")
                    yield CommandOutput(id="adb-output")

    async def on_mount(self) -> None:
        # Fade in sidebar items
        items = self.query(".op-list-item")
        for i, item in enumerate(items):
            item.styles.opacity = 0.0
        for i, item in enumerate(items):
            self.set_timer(0.05 * (i + 1), lambda w=item: self._fade_in(w))

    def _fade_in(self, widget) -> None:
        widget.styles.animate("opacity", value=1.0, duration=0.3)

    def _execute_command(self, cmd_key: str) -> None:
        """Route command execution based on key."""
        if cmd_key == "devices":
            self.run_worker(self._run_devices())
        elif cmd_key == "sideload":
            self.app.push_screen(InputDialog(
                "ADB Sideload",
                "Path to ZIP file...",
                self._do_sideload,
            ))
        elif cmd_key.startswith("reboot_"):
            mode = cmd_key.replace("reboot_", "")
            if mode == "system":
                mode = ""
            self.app.push_screen(ConfirmDialog(
                "⚠ Confirm Reboot",
                f"Reboot device to {'system' if not mode else mode}?",
                lambda m=mode: self.run_worker(self._run_reboot(m)),
            ))
        elif cmd_key == "push":
            self.app.push_screen(InputDialog(
                "ADB Push",
                "Local file path",
                self._do_push,
                fields=[("Local file path...", "input_local"), ("Remote path (e.g. /sdcard/)...", "input_remote")],
            ))
        elif cmd_key == "pull":
            self.app.push_screen(InputDialog(
                "ADB Pull",
                "Remote file path",
                self._do_pull,
                fields=[("Remote file path...", "input_remote"), ("Local save path...", "input_local")],
            ))
        elif cmd_key == "install":
            self.app.push_screen(InputDialog(
                "Install APK",
                "Path to APK file...",
                self._do_install,
            ))
        elif cmd_key == "install_multiple":
            self.app.push_screen(InputDialog(
                "Install Multiple APKs",
                "APK paths (space-separated)...",
                self._do_install_multiple,
            ))
        elif cmd_key == "uninstall":
            self.app.push_screen(InputDialog(
                "Uninstall Package",
                "Package name (e.g. com.example.app)...",
                self._do_uninstall,
            ))
        elif cmd_key == "logcat":
            self.run_worker(self._run_logcat())
        elif cmd_key == "shell":
            self.app.push_screen(InputDialog(
                "Shell Command",
                "Command to run...",
                self._do_shell,
            ))
        elif cmd_key == "bugreport":
            self.app.push_screen(InputDialog(
                "Bugreport",
                "Output path (leave blank for default)...",
                self._do_bugreport,
            ))
        # ── Networking ──
        elif cmd_key == "connect":
            self.app.push_screen(InputDialog(
                "Connect (TCP/IP)",
                "HOST[:PORT] (default port=5555)...",
                self._do_connect,
            ))
        elif cmd_key == "disconnect":
            self.app.push_screen(InputDialog(
                "Disconnect",
                "HOST[:PORT] (leave blank for all)...",
                self._do_disconnect,
            ))
        elif cmd_key == "pair":
            self.app.push_screen(InputDialog(
                "Pair Device",
                "HOST[:PORT]...",
                self._do_pair,
                fields=[("HOST[:PORT]...", "input_host"), ("Pairing code...", "input_code")],
            ))
        elif cmd_key == "tcpip":
            self.app.push_screen(InputDialog(
                "TCP/IP Mode",
                "Port (default: 5555)...",
                self._do_tcpip,
            ))
        elif cmd_key == "usb":
            self.run_worker(self._run_simple("adb usb", adb_usb()))
        elif cmd_key == "forward":
            self.app.push_screen(InputDialog(
                "Forward Port",
                "Local (e.g. tcp:8080)...",
                self._do_forward,
                fields=[("Local (e.g. tcp:8080)...", "input_local"), ("Remote (e.g. tcp:80)...", "input_remote")],
            ))
        elif cmd_key == "forward_list":
            self.run_worker(self._run_simple("adb forward --list", adb_forward_list()))
        elif cmd_key == "reverse":
            self.app.push_screen(InputDialog(
                "Reverse Port",
                "Remote (e.g. tcp:8080)...",
                self._do_reverse,
                fields=[("Remote (e.g. tcp:8080)...", "input_remote"), ("Local (e.g. tcp:80)...", "input_local")],
            ))
        elif cmd_key == "reverse_list":
            self.run_worker(self._run_simple("adb reverse --list", adb_reverse_list()))
        # ── Root / Remount ──
        elif cmd_key == "root":
            self.run_worker(self._run_simple("adb root", adb_root()))
        elif cmd_key == "unroot":
            self.run_worker(self._run_simple("adb unroot", adb_unroot()))
        elif cmd_key == "remount":
            self.run_worker(self._run_simple("adb remount", adb_remount()))
        # ── Security ──
        elif cmd_key == "disable_verity":
            self.app.push_screen(ConfirmDialog(
                "⚠ Disable Verity",
                "Disable dm-verity? Requires userdebug build.\nDevice will need reboot.",
                lambda: self.run_worker(self._run_simple("adb disable-verity", adb_disable_verity())),
            ))
        elif cmd_key == "enable_verity":
            self.run_worker(self._run_simple("adb enable-verity", adb_enable_verity()))
        # ── Server ──
        elif cmd_key == "start_server":
            self.run_worker(self._run_simple("adb start-server", adb_start_server()))
        elif cmd_key == "kill_server":
            self.run_worker(self._run_simple("adb kill-server", adb_kill_server()))
        elif cmd_key == "reconnect":
            self.run_worker(self._run_simple("adb reconnect", adb_reconnect()))
        # ── Scripting ──
        elif cmd_key == "wait_for_device":
            self.run_worker(self._run_simple("adb wait-for-device", adb_wait_for_device()))
        elif cmd_key == "get_state":
            self.run_worker(self._run_simple("adb get-state", adb_get_state()))
        elif cmd_key == "get_serialno":
            self.run_worker(self._run_simple("adb get-serialno", adb_get_serialno()))
        elif cmd_key == "get_devpath":
            self.run_worker(self._run_simple("adb get-devpath", adb_get_devpath()))

    def _set_status(self, status: CmdStatus) -> None:
        self.query_one("#adb-status", StatusIndicator).status = status

    def _get_output(self) -> CommandOutput:
        return self.query_one("#adb-output", CommandOutput)

    # ── Generic simple command worker ──

    async def _run_simple(self, cmd_str: str, coro) -> None:
        """Run a simple command and display the result."""
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(cmd_str)
        result = await coro
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        label = cmd_str.split()[1] if len(cmd_str.split()) > 1 else cmd_str
        status_text = f"{label} {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}"
        output.log_status(status_text, result.status)
        self._set_status(result.status)

    # ── Command workers ──

    async def _run_devices(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("adb devices -l")
        result = await adb_devices()
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Exit code: {result.return_code}", result.status)
        self._set_status(result.status)

    def _do_sideload(self, filepath: str) -> None:
        if filepath.strip():
            self.run_worker(self._run_sideload(filepath.strip()))

    async def _run_sideload(self, filepath: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"adb sideload {filepath}")
        result = await adb_sideload(filepath)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Sideload {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_reboot(self, mode: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        cmd_str = f"adb reboot {mode}" if mode else "adb reboot"
        output.log_command(cmd_str)
        result = await adb_reboot(mode)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Reboot {'sent' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_push(self, local: str, remote: str) -> None:
        if local.strip() and remote.strip():
            self.run_worker(self._run_push(local.strip(), remote.strip()))

    async def _run_push(self, local: str, remote: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"adb push {local} {remote}")
        result = await adb_push(local, remote)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Push {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_pull(self, remote: str, local: str) -> None:
        if remote.strip() and local.strip():
            self.run_worker(self._run_pull(remote.strip(), local.strip()))

    async def _run_pull(self, remote: str, local: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"adb pull {remote} {local}")
        result = await adb_pull(remote, local)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Pull {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_install(self, apk: str) -> None:
        if apk.strip():
            self.run_worker(self._run_install(apk.strip()))

    async def _run_install(self, apk: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"adb install -r {apk}")
        result = await adb_install(apk)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Install {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_install_multiple(self, paths_str: str) -> None:
        paths = paths_str.strip().split()
        if paths:
            self.run_worker(self._run_install_multiple(paths))

    async def _run_install_multiple(self, apk_paths: list[str]) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"adb install-multiple -r {' '.join(apk_paths)}")
        result = await adb_install_multiple(apk_paths)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Install {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_uninstall(self, package: str) -> None:
        if package.strip():
            self.run_worker(self._run_uninstall(package.strip()))

    async def _run_uninstall(self, package: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"adb uninstall {package}")
        result = await adb_uninstall(package)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Uninstall {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_logcat(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("adb logcat -d -t 100")
        result = await adb_logcat()
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Logcat {'captured' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_shell(self, command: str) -> None:
        if command.strip():
            self.run_worker(self._run_shell(command.strip()))

    async def _run_shell(self, command: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"adb shell {command}")
        result = await adb_shell(command)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Shell {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_bugreport(self, path: str) -> None:
        self.run_worker(self._run_bugreport(path.strip()))

    async def _run_bugreport(self, path: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        cmd_str = f"adb bugreport {path}" if path else "adb bugreport"
        output.log_command(cmd_str)
        result = await adb_bugreport(path)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Bugreport {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    # ── Networking workers ──

    def _do_connect(self, host_port: str) -> None:
        if host_port.strip():
            self.run_worker(self._run_simple(f"adb connect {host_port.strip()}", adb_connect(host_port.strip())))

    def _do_disconnect(self, host_port: str) -> None:
        hp = host_port.strip()
        cmd_str = f"adb disconnect {hp}" if hp else "adb disconnect"
        self.run_worker(self._run_simple(cmd_str, adb_disconnect(hp)))

    def _do_pair(self, host_port: str, code: str) -> None:
        if host_port.strip():
            self.run_worker(self._run_simple(
                f"adb pair {host_port.strip()} {code.strip()}",
                adb_pair(host_port.strip(), code.strip()),
            ))

    def _do_tcpip(self, port_str: str) -> None:
        port = int(port_str.strip()) if port_str.strip().isdigit() else 5555
        self.run_worker(self._run_simple(f"adb tcpip {port}", adb_tcpip(port)))

    def _do_forward(self, local: str, remote: str) -> None:
        if local.strip() and remote.strip():
            self.run_worker(self._run_simple(
                f"adb forward {local.strip()} {remote.strip()}",
                adb_forward(local.strip(), remote.strip()),
            ))

    def _do_reverse(self, remote: str, local: str) -> None:
        if remote.strip() and local.strip():
            self.run_worker(self._run_simple(
                f"adb reverse {remote.strip()} {local.strip()}",
                adb_reverse(remote.strip(), local.strip()),
            ))

    # ── Navigation ──

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-screen":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
