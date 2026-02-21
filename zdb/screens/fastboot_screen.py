"""Fastboot operations screen with command sidebar and output panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from zdb.backend import (
    CmdStatus,
    fastboot_boot,
    fastboot_create_logical_partition,
    fastboot_delete_logical_partition,
    fastboot_devices,
    fastboot_erase,
    fastboot_fetch,
    fastboot_flash,
    fastboot_flashall,
    fastboot_flashing,
    fastboot_format,
    fastboot_get_staged,
    fastboot_getvar,
    fastboot_gsi,
    fastboot_oem,
    fastboot_reboot,
    fastboot_resize_logical_partition,
    fastboot_set_active,
    fastboot_snapshot_update,
    fastboot_stage,
    fastboot_update,
    fastboot_wipe_super,
)
from zdb.screens.adb_screen import ConfirmDialog, InputDialog
from zdb.widgets.command_output import CommandOutput
from zdb.widgets.status_bar import StatusIndicator


FASTBOOT_COMMANDS = [
    ("─── Device ───", None),
    ("  📋  List Devices", "devices"),
    ("─── Flashing ───", None),
    ("  💾  Flash Partition", "flash"),
    ("  📦  Update ZIP (flash all)", "update"),
    ("  💾  Flash All ($OUT)", "flashall"),
    ("  🖼   Boot Image (no flash)", "boot"),
    ("─── Info ───", None),
    ("  🔎  GetVar — product", "getvar_product"),
    ("  🔎  GetVar — all", "getvar_all"),
    ("  🔎  GetVar — custom", "getvar_custom"),
    ("─── Erase / Format ───", None),
    ("  🗑   Erase Partition", "erase"),
    ("  📝  Format Partition", "format"),
    ("─── Slots ───", None),
    ("  🔀  Set Active Slot", "set_active"),
    ("─── Logical Partition ───", None),
    ("  ➕  Create Logical Partition", "create_logical"),
    ("  ➖  Delete Logical Partition", "delete_logical"),
    ("  📐  Resize Logical Partition", "resize_logical"),
    ("─── Bootloader ───", None),
    ("  🔓  Flashing Unlock", "flashing_unlock"),
    ("  🔒  Flashing Lock", "flashing_lock"),
    ("  🔓  Unlock Critical", "flashing_unlock_critical"),
    ("  🔒  Lock Critical", "flashing_lock_critical"),
    ("  🔑  Get Unlock Ability", "flashing_get_unlock_ability"),
    ("  🔓  OEM Unlock", "oem_unlock"),
    ("  🔒  OEM Lock", "oem_lock"),
    ("  📟  OEM Command (custom)", "oem_custom"),
    ("─── Advanced ───", None),
    ("  🔄  GSI Wipe", "gsi_wipe"),
    ("  🔄  GSI Disable", "gsi_disable"),
    ("  📊  GSI Status", "gsi_status"),
    ("  💥  Wipe Super", "wipe_super"),
    ("  📸  Snapshot Update Cancel", "snapshot_cancel"),
    ("  📸  Snapshot Update Merge", "snapshot_merge"),
    ("  📥  Fetch Partition Image", "fetch"),
    ("─── Android Things ───", None),
    ("  📤  Stage File", "stage"),
    ("  📥  Get Staged File", "get_staged"),
    ("─── Reboot ───", None),
    ("  🔄  Reboot → System", "reboot"),
    ("  🔄  Reboot → Bootloader", "reboot_bootloader"),
    ("  🔄  Reboot → Fastboot", "reboot_fastboot"),
]


COMMON_PARTITIONS = [
    "boot", "recovery", "system", "vendor", "dtbo",
    "vbmeta", "super", "userdata", "cache", "radio",
    "modem", "aboot", "sbl1", "tz", "rpm",
    "init_boot", "vendor_boot", "product", "odm",
]


class FastbootMenuItem(Static, can_focus=True):
    """A focusable menu item in the Fastboot sidebar."""

    def __init__(self, label: str, cmd_key: str | None, **kwargs):
        super().__init__(label, **kwargs)
        self._cmd_key = cmd_key

    def on_click(self) -> None:
        if self._cmd_key:
            self.screen._execute_command(self._cmd_key)


class FastbootScreen(Screen):
    """Fastboot operations screen."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="op-screen"):
            with Container(classes="op-header"):
                yield Static(
                    "⚡ Fastboot Operations  —  [bold #484f58]ESC[/] Back",
                    classes="op-header-title",
                )
                yield Button("✕ Close", id="btn-close-screen", classes="header-close-btn")

            with Horizontal(classes="op-body"):
                with Vertical(classes="op-sidebar"):
                    for label, cmd_key in FASTBOOT_COMMANDS:
                        if cmd_key is None:
                            yield Static(label, classes="op-category-label")
                        else:
                            yield FastbootMenuItem(label, cmd_key, classes="op-list-item")

                with Vertical(classes="op-content"):
                    yield StatusIndicator(id="fb-status")
                    yield CommandOutput(id="fb-output")

    async def on_mount(self) -> None:
        items = self.query(".op-list-item")
        for i, item in enumerate(items):
            item.styles.opacity = 0.0
        for i, item in enumerate(items):
            self.set_timer(0.05 * (i + 1), lambda w=item: self._fade_in(w))

    def _fade_in(self, widget) -> None:
        widget.styles.animate("opacity", value=1.0, duration=0.3)

    def _execute_command(self, cmd_key: str) -> None:
        if cmd_key == "devices":
            self.run_worker(self._run_devices())
        elif cmd_key == "flash":
            partitions_hint = ", ".join(COMMON_PARTITIONS[:8]) + "..."
            self.app.push_screen(InputDialog(
                "Flash Partition",
                f"Partition name ({partitions_hint})",
                self._do_flash,
                fields=[
                    (f"Partition ({partitions_hint})...", "input_partition"),
                    ("Image file path...", "input_image"),
                ],
            ))
        elif cmd_key == "update":
            self.app.push_screen(InputDialog(
                "Update ZIP",
                "Path to update.zip...",
                self._do_update,
            ))
        elif cmd_key == "flashall":
            self.app.push_screen(ConfirmDialog(
                "⚠ Flash All",
                "Flash ALL partitions from $ANDROID_PRODUCT_OUT?\nThis is IRREVERSIBLE!",
                lambda: self.run_worker(self._run_flashall()),
            ))
        elif cmd_key == "boot":
            self.app.push_screen(InputDialog(
                "Boot Image",
                "Path to boot image...",
                self._do_boot,
            ))
        elif cmd_key == "getvar_product":
            self.run_worker(self._run_getvar("product"))
        elif cmd_key == "getvar_all":
            self.run_worker(self._run_getvar("all"))
        elif cmd_key == "getvar_custom":
            self.app.push_screen(InputDialog(
                "GetVar",
                "Variable name...",
                lambda v: self.run_worker(self._run_getvar(v)),
            ))
        elif cmd_key == "erase":
            self.app.push_screen(InputDialog(
                "Erase Partition",
                "Partition name...",
                self._do_erase,
            ))
        elif cmd_key == "format":
            self.app.push_screen(InputDialog(
                "Format Partition",
                "Partition name...",
                self._do_format,
                fields=[
                    ("Partition name...", "input_partition"),
                    ("Filesystem type (optional, e.g. ext4)...", "input_fstype"),
                    ("Size (optional)...", "input_size"),
                ],
            ))
        elif cmd_key == "set_active":
            self.app.push_screen(InputDialog(
                "Set Active Slot",
                "Slot name (a / b)...",
                self._do_set_active,
            ))
        elif cmd_key == "create_logical":
            self.app.push_screen(InputDialog(
                "Create Logical Partition",
                "Partition name...",
                self._do_create_logical,
                fields=[
                    ("Partition name...", "input_partition"),
                    ("Size in bytes...", "input_size"),
                ],
            ))
        elif cmd_key == "delete_logical":
            self.app.push_screen(InputDialog(
                "Delete Logical Partition",
                "Partition name...",
                self._do_delete_logical,
            ))
        elif cmd_key == "resize_logical":
            self.app.push_screen(InputDialog(
                "Resize Logical Partition",
                "Partition name...",
                self._do_resize_logical,
                fields=[
                    ("Partition name...", "input_partition"),
                    ("New size in bytes...", "input_size"),
                ],
            ))
        elif cmd_key == "flashing_unlock":
            self.app.push_screen(ConfirmDialog(
                "⚠ DANGER — Unlock Bootloader",
                "This will ERASE ALL DATA!\nAre you absolutely sure?",
                lambda: self.run_worker(self._run_flashing("unlock")),
            ))
        elif cmd_key == "flashing_lock":
            self.app.push_screen(ConfirmDialog(
                "⚠ Lock Bootloader",
                "Lock the bootloader? This may erase data.",
                lambda: self.run_worker(self._run_flashing("lock")),
            ))
        elif cmd_key == "flashing_unlock_critical":
            self.app.push_screen(ConfirmDialog(
                "⚠ DANGER — Unlock Critical Partitions",
                "Unlock CRITICAL bootloader partitions?\nThis is extremely dangerous!",
                lambda: self.run_worker(self._run_flashing("unlock_critical")),
            ))
        elif cmd_key == "flashing_lock_critical":
            self.app.push_screen(ConfirmDialog(
                "⚠ Lock Critical Partitions",
                "Lock critical bootloader partitions?",
                lambda: self.run_worker(self._run_flashing("lock_critical")),
            ))
        elif cmd_key == "flashing_get_unlock_ability":
            self.run_worker(self._run_flashing("get_unlock_ability"))
        elif cmd_key == "oem_unlock":
            self.app.push_screen(ConfirmDialog(
                "⚠ DANGER — OEM Unlock",
                "This will ERASE ALL DATA!\nAre you absolutely sure?",
                lambda: self.run_worker(self._run_oem("unlock")),
            ))
        elif cmd_key == "oem_lock":
            self.app.push_screen(ConfirmDialog(
                "⚠ OEM Lock",
                "Lock via OEM? This may erase data.",
                lambda: self.run_worker(self._run_oem("lock")),
            ))
        elif cmd_key == "oem_custom":
            self.app.push_screen(InputDialog(
                "OEM Command",
                "OEM command to run...",
                lambda c: self.run_worker(self._run_oem(c)),
            ))
        # ── Advanced ──
        elif cmd_key == "gsi_wipe":
            self.app.push_screen(ConfirmDialog(
                "⚠ GSI Wipe",
                "Wipe GSI installation? (fastbootd only)",
                lambda: self.run_worker(self._run_gsi("wipe")),
            ))
        elif cmd_key == "gsi_disable":
            self.run_worker(self._run_gsi("disable"))
        elif cmd_key == "gsi_status":
            self.run_worker(self._run_gsi("status"))
        elif cmd_key == "wipe_super":
            self.app.push_screen(ConfirmDialog(
                "⚠ Wipe Super Partition",
                "Reset super to empty default dynamic partitions?\nThis is IRREVERSIBLE!",
                lambda: self.run_worker(self._run_wipe_super()),
            ))
        elif cmd_key == "snapshot_cancel":
            self.run_worker(self._run_snapshot_update("cancel"))
        elif cmd_key == "snapshot_merge":
            self.run_worker(self._run_snapshot_update("merge"))
        elif cmd_key == "fetch":
            self.app.push_screen(InputDialog(
                "Fetch Partition Image",
                "Partition name...",
                self._do_fetch,
                fields=[
                    ("Partition name...", "input_partition"),
                    ("Output file path...", "input_outfile"),
                ],
            ))
        elif cmd_key == "stage":
            self.app.push_screen(InputDialog(
                "Stage File",
                "Path to file to stage...",
                self._do_stage,
            ))
        elif cmd_key == "get_staged":
            self.app.push_screen(InputDialog(
                "Get Staged File",
                "Output file path...",
                self._do_get_staged,
            ))
        elif cmd_key == "reboot":
            self.run_worker(self._run_reboot(""))
        elif cmd_key == "reboot_bootloader":
            self.run_worker(self._run_reboot("bootloader"))
        elif cmd_key == "reboot_fastboot":
            self.run_worker(self._run_reboot("fastboot"))

    def _set_status(self, status: CmdStatus) -> None:
        self.query_one("#fb-status", StatusIndicator).status = status

    def _get_output(self) -> CommandOutput:
        return self.query_one("#fb-output", CommandOutput)

    # ── Generic simple worker ──

    async def _run_simple(self, cmd_str: str, coro) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(cmd_str)
        result = await coro
        combined = (result.stdout + "\n" + result.stderr).strip()
        output.log_output(combined, result.status)
        label = cmd_str.split()[1] if len(cmd_str.split()) > 1 else cmd_str
        output.log_status(f"{label} {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    # ── Workers ──

    async def _run_devices(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("fastboot devices")
        result = await fastboot_devices()
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, CmdStatus.FAILED)
        output.log_status(f"Exit code: {result.return_code}", result.status)
        self._set_status(result.status)

    def _do_flash(self, partition: str, image: str) -> None:
        if partition.strip() and image.strip():
            self.app.push_screen(ConfirmDialog(
                f"⚠ Confirm Flash — {partition.strip()}",
                f"Flash '{image.strip()}' to partition '{partition.strip()}'?\nThis is irreversible!",
                lambda: self.run_worker(self._run_flash(partition.strip(), image.strip())),
            ))

    async def _run_flash(self, partition: str, image: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot flash {partition} {image}")
        result = await fastboot_flash(partition, image)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Flash {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_update(self, zip_path: str) -> None:
        if zip_path.strip():
            self.app.push_screen(ConfirmDialog(
                "⚠ Confirm Update",
                f"Flash ALL partitions from '{zip_path.strip()}'?\nThis is IRREVERSIBLE!",
                lambda: self.run_worker(self._run_update(zip_path.strip())),
            ))

    async def _run_update(self, zip_path: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot update {zip_path}")
        result = await fastboot_update(zip_path)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Update {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_flashall(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("fastboot flashall")
        result = await fastboot_flashall()
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Flashall {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_boot(self, image: str) -> None:
        if image.strip():
            self.run_worker(self._run_boot(image.strip()))

    async def _run_boot(self, image: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot boot {image}")
        result = await fastboot_boot(image)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Boot {'sent' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_getvar(self, var: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot getvar {var}")
        result = await fastboot_getvar(var)
        # fastboot getvar sends output to stderr
        combined = (result.stdout + "\n" + result.stderr).strip()
        output.log_output(combined, result.status)
        output.log_status(f"GetVar {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_erase(self, partition: str) -> None:
        if partition.strip():
            self.app.push_screen(ConfirmDialog(
                f"⚠ Confirm Erase — {partition.strip()}",
                f"Erase partition '{partition.strip()}'?\nThis is IRREVERSIBLE!",
                lambda: self.run_worker(self._run_erase(partition.strip())),
            ))

    async def _run_erase(self, partition: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot erase {partition}")
        result = await fastboot_erase(partition)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Erase {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_format(self, partition: str, fs_type: str, size: str) -> None:
        if partition.strip():
            self.app.push_screen(ConfirmDialog(
                f"⚠ Confirm Format — {partition.strip()}",
                f"Format partition '{partition.strip()}'?\nThis is IRREVERSIBLE!",
                lambda: self.run_worker(self._run_format(partition.strip(), fs_type.strip(), size.strip())),
            ))

    async def _run_format(self, partition: str, fs_type: str, size: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        fmt_str = "format"
        if fs_type:
            fmt_str += f":{fs_type}"
            if size:
                fmt_str += f":{size}"
        output.log_command(f"fastboot {fmt_str} {partition}")
        result = await fastboot_format(partition, fs_type, size)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Format {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_set_active(self, slot: str) -> None:
        if slot.strip():
            self.run_worker(self._run_set_active(slot.strip()))

    async def _run_set_active(self, slot: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot set_active {slot}")
        result = await fastboot_set_active(slot)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Set active slot {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_create_logical(self, name: str, size: str) -> None:
        if name.strip() and size.strip():
            self.run_worker(self._run_create_logical(name.strip(), size.strip()))

    async def _run_create_logical(self, name: str, size: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot create-logical-partition {name} {size}")
        result = await fastboot_create_logical_partition(name, size)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(
            f"Create logical partition {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}",
            result.status,
        )
        self._set_status(result.status)

    def _do_delete_logical(self, name: str) -> None:
        if name.strip():
            self.app.push_screen(ConfirmDialog(
                f"⚠ Confirm Delete — {name.strip()}",
                f"Delete logical partition '{name.strip()}'?\nThis is IRREVERSIBLE!",
                lambda: self.run_worker(self._run_delete_logical(name.strip())),
            ))

    async def _run_delete_logical(self, name: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot delete-logical-partition {name}")
        result = await fastboot_delete_logical_partition(name)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(
            f"Delete logical partition {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}",
            result.status,
        )
        self._set_status(result.status)

    def _do_resize_logical(self, name: str, size: str) -> None:
        if name.strip() and size.strip():
            self.run_worker(self._run_resize_logical(name.strip(), size.strip()))

    async def _run_resize_logical(self, name: str, size: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot resize-logical-partition {name} {size}")
        result = await fastboot_resize_logical_partition(name, size)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(
            f"Resize logical partition {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}",
            result.status,
        )
        self._set_status(result.status)

    async def _run_flashing(self, action: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot flashing {action}")
        result = await fastboot_flashing(action)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Flashing {action} {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_oem(self, action: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot oem {action}")
        result = await fastboot_oem(action)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"OEM {action} {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_gsi(self, action: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot gsi {action}")
        result = await fastboot_gsi(action)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"GSI {action} {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_wipe_super(self) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command("fastboot wipe-super")
        result = await fastboot_wipe_super()
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Wipe super {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_snapshot_update(self, action: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot snapshot-update {action}")
        result = await fastboot_snapshot_update(action)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Snapshot {action} {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_fetch(self, partition: str, out_file: str) -> None:
        if partition.strip() and out_file.strip():
            self.run_worker(self._run_fetch(partition.strip(), out_file.strip()))

    async def _run_fetch(self, partition: str, out_file: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot fetch {partition} {out_file}")
        result = await fastboot_fetch(partition, out_file)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Fetch {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_stage(self, in_file: str) -> None:
        if in_file.strip():
            self.run_worker(self._run_stage(in_file.strip()))

    async def _run_stage(self, in_file: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot stage {in_file}")
        result = await fastboot_stage(in_file)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Stage {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def _do_get_staged(self, out_file: str) -> None:
        if out_file.strip():
            self.run_worker(self._run_get_staged(out_file.strip()))

    async def _run_get_staged(self, out_file: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        output.log_command(f"fastboot get_staged {out_file}")
        result = await fastboot_get_staged(out_file)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Get staged {'complete' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    async def _run_reboot(self, mode: str) -> None:
        output = self._get_output()
        self._set_status(CmdStatus.RUNNING)
        cmd_str = f"fastboot reboot {mode}" if mode else "fastboot reboot"
        output.log_command(cmd_str)
        result = await fastboot_reboot(mode)
        output.log_output(result.stdout, result.status)
        if result.stderr:
            output.log_output(result.stderr, result.status)
        output.log_status(f"Reboot {'sent' if result.status == CmdStatus.SUCCESS else 'failed'}", result.status)
        self._set_status(result.status)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-screen":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
