"""
ADB/Fastboot backend — async command execution layer.
Wraps adb and fastboot CLI tools with status tracking.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Target device tracking ───────────────────────────────────────────
_target_serial: str = ""


class CmdStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    AUTH_REQUIRED = "auth_required"


@dataclass
class CmdResult:
    status: CmdStatus = CmdStatus.IDLE
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1


@dataclass
class DeviceInfo:
    serial: str = ""
    model: str = ""
    manufacturer: str = ""
    brand: str = ""
    codename: str = ""
    chipset: str = ""
    soc: str = ""
    cpu_arch: str = ""
    cpu_cores: str = ""
    cpu_freq: str = ""
    ram_total: str = ""
    ram_available: str = ""
    storage_total: str = ""
    storage_used: str = ""
    storage_free: str = ""
    imei: str = ""
    meid: str = ""
    sim_slots: str = ""
    sim_operator: str = ""
    sim_provider: str = ""
    esim_support: str = ""
    screen_resolution: str = ""
    screen_dpi: str = ""
    screen_refresh_rate: str = ""
    android_version: str = ""
    sdk_level: str = ""
    security_patch: str = ""
    build_number: str = ""
    kernel_version: str = ""
    battery_level: str = ""
    battery_health: str = ""
    battery_temp: str = ""
    charging_status: str = ""
    connection_type: str = ""
    auth_status: str = ""


async def run_cmd(cmd: list[str], timeout: float = 30.0) -> CmdResult:
    """Execute a shell command asynchronously and return the result."""
    result = CmdResult(status=CmdStatus.RUNNING)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            result.status = CmdStatus.FAILED
            result.stderr = "Command timed out"
            result.return_code = -1
            return result

        result.stdout = stdout_bytes.decode("utf-8", errors="replace")
        result.stderr = stderr_bytes.decode("utf-8", errors="replace")
        result.return_code = proc.returncode or 0

        if "unauthorized" in result.stdout.lower() or "unauthorized" in result.stderr.lower():
            result.status = CmdStatus.AUTH_REQUIRED
        elif result.return_code == 0:
            result.status = CmdStatus.SUCCESS
        else:
            result.status = CmdStatus.FAILED

    except FileNotFoundError:
        result.status = CmdStatus.FAILED
        result.stderr = f"Command not found: {cmd[0]}"
    except Exception as e:
        result.status = CmdStatus.FAILED
        result.stderr = str(e)

    return result


async def run_cmd_sudo(cmd: list[str], password: str, timeout: float = 30.0) -> CmdResult:
    """Execute a command with sudo, piping the password via stdin.

    Wraps the command with `sudo -S` and feeds the password to stdin.
    """
    result = CmdResult(status=CmdStatus.RUNNING)

    # Build sudo command: replace leading 'sudo' if present, or prepend it
    if cmd and cmd[0] == "sudo":
        sudo_cmd = ["sudo", "-S"] + cmd[1:]
    else:
        sudo_cmd = ["sudo", "-S"] + cmd

    try:
        proc = await asyncio.create_subprocess_exec(
            *sudo_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdin_data = (password + "\n").encode("utf-8")
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=stdin_data), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            result.status = CmdStatus.FAILED
            result.stderr = "Command timed out"
            result.return_code = -1
            return result

        result.stdout = stdout_bytes.decode("utf-8", errors="replace")
        result.stderr = stderr_bytes.decode("utf-8", errors="replace")
        result.return_code = proc.returncode or 0

        # Filter out the password prompt from stderr
        stderr_lines = []
        for line in result.stderr.splitlines():
            if "[sudo]" in line or "password for" in line.lower() or "Password:" in line:
                continue
            stderr_lines.append(line)
        result.stderr = "\n".join(stderr_lines).strip()

        if "incorrect password" in result.stderr.lower() or "sorry" in result.stderr.lower():
            result.status = CmdStatus.AUTH_REQUIRED
            result.stderr = "Incorrect password"
        elif result.return_code == 0:
            result.status = CmdStatus.SUCCESS
        else:
            result.status = CmdStatus.FAILED

    except FileNotFoundError:
        result.status = CmdStatus.FAILED
        result.stderr = "sudo not found"
    except Exception as e:
        result.status = CmdStatus.FAILED
        result.stderr = str(e)

    return result


# ── ADB Commands ──────────────────────────────────────────────────────

async def adb_devices() -> CmdResult:
    return await run_cmd(["adb", "devices", "-l"])


async def adb_sideload(filepath: str) -> CmdResult:
    return await run_cmd(["adb", "sideload", filepath], timeout=600.0)


async def adb_reboot(mode: str = "") -> CmdResult:
    cmd = ["adb", "reboot"]
    if mode:
        cmd.append(mode)
    return await run_cmd(cmd)


async def adb_push(local: str, remote: str) -> CmdResult:
    return await run_cmd(["adb", "push", local, remote], timeout=300.0)


async def adb_pull(remote: str, local: str) -> CmdResult:
    return await run_cmd(["adb", "pull", remote, local], timeout=300.0)


async def adb_install(apk_path: str) -> CmdResult:
    return await run_cmd(["adb", "install", "-r", apk_path], timeout=120.0)


async def adb_uninstall(package: str) -> CmdResult:
    return await run_cmd(["adb", "uninstall", package])


async def adb_shell(command: str) -> CmdResult:
    return await run_cmd(["adb", "shell", command])


async def adb_logcat(lines: int = 100) -> CmdResult:
    return await run_cmd(["adb", "logcat", "-d", "-t", str(lines)], timeout=15.0)


async def adb_get_prop(prop: str) -> str:
    """Get a single device property."""
    r = await run_cmd(["adb", "shell", "getprop", prop])
    return r.stdout.strip() if r.status == CmdStatus.SUCCESS else ""


async def adb_shell_cmd(command: str) -> str:
    """Run a shell command and return raw stdout."""
    r = await run_cmd(["adb", "shell", command])
    return r.stdout.strip() if r.status == CmdStatus.SUCCESS else ""


# ── ADB: Networking ──────────────────────────────────────────────────

async def adb_connect(host_port: str) -> CmdResult:
    """Connect to a device via TCP/IP."""
    return await run_cmd(["adb", "connect", host_port])


async def adb_disconnect(host_port: str = "") -> CmdResult:
    """Disconnect from TCP/IP device(s)."""
    cmd = ["adb", "disconnect"]
    if host_port:
        cmd.append(host_port)
    return await run_cmd(cmd)


async def adb_pair(host_port: str, pairing_code: str = "") -> CmdResult:
    """Pair with a device for secure TCP/IP communication."""
    cmd = ["adb", "pair", host_port]
    if pairing_code:
        cmd.append(pairing_code)
    return await run_cmd(cmd)


async def adb_forward(local: str, remote: str) -> CmdResult:
    """Forward a socket connection."""
    return await run_cmd(["adb", "forward", local, remote])


async def adb_forward_list() -> CmdResult:
    """List all forward socket connections."""
    return await run_cmd(["adb", "forward", "--list"])


async def adb_forward_remove(local: str) -> CmdResult:
    """Remove a specific forward socket connection."""
    return await run_cmd(["adb", "forward", "--remove", local])


async def adb_reverse(remote: str, local: str) -> CmdResult:
    """Reverse a socket connection."""
    return await run_cmd(["adb", "reverse", remote, local])


async def adb_reverse_list() -> CmdResult:
    """List all reverse socket connections."""
    return await run_cmd(["adb", "reverse", "--list"])


async def adb_reverse_remove(remote: str) -> CmdResult:
    """Remove a specific reverse socket connection."""
    return await run_cmd(["adb", "reverse", "--remove", remote])


async def adb_tcpip(port: int = 5555) -> CmdResult:
    """Restart adbd listening on TCP on PORT."""
    return await run_cmd(["adb", "tcpip", str(port)])


async def adb_usb() -> CmdResult:
    """Restart adbd listening on USB."""
    return await run_cmd(["adb", "usb"])


# ── ADB: Debug & Security ───────────────────────────────────────────

async def adb_bugreport(path: str = "") -> CmdResult:
    """Write bugreport to given path."""
    cmd = ["adb", "bugreport"]
    if path:
        cmd.append(path)
    return await run_cmd(cmd, timeout=300.0)


async def adb_install_multiple(apk_paths: list[str]) -> CmdResult:
    """Push multiple APKs for a single package and install them."""
    return await run_cmd(["adb", "install-multiple", "-r"] + apk_paths, timeout=120.0)


async def adb_remount() -> CmdResult:
    """Remount partitions read-write."""
    return await run_cmd(["adb", "remount"])


async def adb_root() -> CmdResult:
    """Restart adbd with root permissions."""
    return await run_cmd(["adb", "root"])


async def adb_unroot() -> CmdResult:
    """Restart adbd without root permissions."""
    return await run_cmd(["adb", "unroot"])


async def adb_disable_verity() -> CmdResult:
    """Disable dm-verity checking on userdebug builds."""
    return await run_cmd(["adb", "disable-verity"])


async def adb_enable_verity() -> CmdResult:
    """Re-enable dm-verity checking on userdebug builds."""
    return await run_cmd(["adb", "enable-verity"])


# ── ADB: Server & Scripting ─────────────────────────────────────────

async def adb_start_server() -> CmdResult:
    """Ensure that there is a server running."""
    return await run_cmd(["adb", "start-server"])


async def adb_kill_server() -> CmdResult:
    """Kill the server if it is running."""
    return await run_cmd(["adb", "kill-server"])


async def adb_reconnect(target: str = "") -> CmdResult:
    """Kick connection from host/device side to force reconnect."""
    cmd = ["adb", "reconnect"]
    if target:
        cmd.append(target)
    return await run_cmd(cmd)


async def adb_get_state() -> CmdResult:
    """Print offline | bootloader | device."""
    return await run_cmd(["adb", "get-state"])


async def adb_get_serialno() -> CmdResult:
    """Print device serial number."""
    return await run_cmd(["adb", "get-serialno"])


async def adb_get_devpath() -> CmdResult:
    """Print device path."""
    return await run_cmd(["adb", "get-devpath"])


async def adb_wait_for_device() -> CmdResult:
    """Wait for device to be in 'device' state."""
    return await run_cmd(["adb", "wait-for-device"], timeout=120.0)


# ── Fastboot Commands ────────────────────────────────────────────────

async def fastboot_devices() -> CmdResult:
    return await run_cmd(["fastboot", "devices"])


async def fastboot_flash(partition: str, image_path: str) -> CmdResult:
    return await run_cmd(["fastboot", "flash", partition, image_path], timeout=300.0)


async def fastboot_getvar(var: str = "all") -> CmdResult:
    return await run_cmd(["fastboot", "getvar", var])


async def fastboot_oem(action: str) -> CmdResult:
    return await run_cmd(["fastboot", "oem", action])


async def fastboot_erase(partition: str) -> CmdResult:
    return await run_cmd(["fastboot", "erase", partition])


async def fastboot_boot(image_path: str) -> CmdResult:
    return await run_cmd(["fastboot", "boot", image_path], timeout=120.0)


async def fastboot_reboot(mode: str = "") -> CmdResult:
    cmd = ["fastboot", "reboot"]
    if mode:
        cmd.append(mode)
    return await run_cmd(cmd)


async def fastboot_flashing(action: str) -> CmdResult:
    return await run_cmd(["fastboot", "flashing", action])


async def fastboot_create_logical_partition(name: str, size: str) -> CmdResult:
    """Create a logical partition with the given name and size."""
    return await run_cmd(["fastboot", "create-logical-partition", name, size], timeout=60.0)


async def fastboot_delete_logical_partition(name: str) -> CmdResult:
    """Delete a logical partition by name."""
    return await run_cmd(["fastboot", "delete-logical-partition", name], timeout=60.0)


async def fastboot_update(zip_path: str) -> CmdResult:
    """Flash all partitions from an update.zip package."""
    return await run_cmd(["fastboot", "update", zip_path], timeout=600.0)


async def fastboot_flashall() -> CmdResult:
    """Flash all partitions from $ANDROID_PRODUCT_OUT."""
    return await run_cmd(["fastboot", "flashall"], timeout=600.0)


async def fastboot_format(partition: str, fs_type: str = "", size: str = "") -> CmdResult:
    """Format a flash partition."""
    fmt = "format"
    if fs_type:
        fmt += f":{fs_type}"
        if size:
            fmt += f":{size}"
    return await run_cmd(["fastboot", fmt, partition], timeout=120.0)


async def fastboot_set_active(slot: str) -> CmdResult:
    """Set the active slot."""
    return await run_cmd(["fastboot", "set_active", slot])


async def fastboot_gsi(action: str) -> CmdResult:
    """Wipe, disable or show status of a GSI installation (fastbootd only)."""
    return await run_cmd(["fastboot", "gsi", action])


async def fastboot_wipe_super(super_empty: str = "") -> CmdResult:
    """Wipe the super partition."""
    cmd = ["fastboot", "wipe-super"]
    if super_empty:
        cmd.append(super_empty)
    return await run_cmd(cmd, timeout=120.0)


async def fastboot_resize_logical_partition(name: str, size: str) -> CmdResult:
    """Change the size of the named logical partition."""
    return await run_cmd(["fastboot", "resize-logical-partition", name, size], timeout=60.0)


async def fastboot_snapshot_update(action: str) -> CmdResult:
    """Cancel or merge a snapshot-based update."""
    return await run_cmd(["fastboot", "snapshot-update", action])


async def fastboot_fetch(partition: str, out_file: str) -> CmdResult:
    """Fetch a partition image from the device."""
    return await run_cmd(["fastboot", "fetch", partition, out_file], timeout=300.0)


async def fastboot_stage(in_file: str) -> CmdResult:
    """Send given file to stage for the next command."""
    return await run_cmd(["fastboot", "stage", in_file], timeout=120.0)


async def fastboot_get_staged(out_file: str) -> CmdResult:
    """Write data staged by the last command to a file."""
    return await run_cmd(["fastboot", "get_staged", out_file], timeout=120.0)


# ── Device Information Gathering ─────────────────────────────────────

def _parse_meminfo(raw: str) -> tuple[str, str]:
    """Parse /proc/meminfo for total and available RAM."""
    total = avail = ""
    for line in raw.splitlines():
        if line.startswith("MemTotal:"):
            kb = int(re.search(r"(\d+)", line).group(1))
            total = f"{kb / 1024 / 1024:.1f} GB"
        elif line.startswith("MemAvailable:"):
            kb = int(re.search(r"(\d+)", line).group(1))
            avail = f"{kb / 1024 / 1024:.1f} GB"
    return total, avail


def _parse_storage(raw: str) -> tuple[str, str, str]:
    """Parse df output for /data partition."""
    for line in raw.splitlines():
        if "/data" in line:
            parts = line.split()
            if len(parts) >= 4:
                return parts[1], parts[2], parts[3]
    return "", "", ""


def _parse_battery(raw: str) -> dict[str, str]:
    """Parse dumpsys battery output."""
    info: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if "level:" in line:
            info["level"] = line.split(":", 1)[1].strip() + "%"
        elif "health:" in line:
            val = line.split(":", 1)[1].strip()
            health_map = {"2": "Good", "3": "Overheat", "4": "Dead", "5": "Over Voltage", "6": "Failure", "7": "Cold"}
            info["health"] = health_map.get(val, val)
        elif "temperature:" in line:
            try:
                temp = int(line.split(":", 1)[1].strip()) / 10
                info["temp"] = f"{temp:.1f}°C"
            except ValueError:
                info["temp"] = line.split(":", 1)[1].strip()
        elif "status:" in line:
            val = line.split(":", 1)[1].strip()
            status_map = {"1": "Unknown", "2": "Charging", "3": "Discharging", "4": "Not Charging", "5": "Full"}
            info["charging"] = status_map.get(val, val)
    return info


async def get_device_info() -> DeviceInfo | None:
    """Gather comprehensive device information via ADB."""
    # Check connection first
    devices_result = await adb_devices()
    if devices_result.status != CmdStatus.SUCCESS:
        return None

    lines = [l for l in devices_result.stdout.strip().splitlines() if l and not l.startswith("List")]
    if not lines:
        return None

    first_device = lines[0]
    if "unauthorized" in first_device.lower():
        info = DeviceInfo()
        info.auth_status = "⚠ Unauthorized"
        info.serial = first_device.split()[0] if first_device.split() else ""
        return info

    if "device" not in first_device.lower():
        return None

    info = DeviceInfo()
    info.auth_status = "✓ Authorized"
    info.serial = first_device.split()[0] if first_device.split() else ""

    # Gather all properties concurrently
    props = await asyncio.gather(
        adb_get_prop("ro.product.model"),
        adb_get_prop("ro.product.manufacturer"),
        adb_get_prop("ro.product.brand"),
        adb_get_prop("ro.product.device"),
        adb_get_prop("ro.hardware.chipname"),
        adb_get_prop("ro.board.platform"),
        adb_get_prop("ro.product.cpu.abi"),
        adb_get_prop("ro.build.version.release"),
        adb_get_prop("ro.build.version.sdk"),
        adb_get_prop("ro.build.version.security_patch"),
        adb_get_prop("ro.build.display.id"),
        adb_shell_cmd("cat /proc/meminfo"),
        adb_shell_cmd("df -h /data"),
        adb_shell_cmd("dumpsys battery"),
        adb_shell_cmd("wm size"),
        adb_shell_cmd("wm density"),
        adb_get_prop("persist.sys.timezone"),
        adb_shell_cmd("uname -r"),
        adb_get_prop("gsm.sim.operator.alpha"),
        adb_get_prop("gsm.operator.alpha"),
        adb_shell_cmd("getprop gsm.sim.state"),
        adb_shell_cmd("nproc"),
        adb_shell_cmd("cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq 2>/dev/null || echo ''"),
        adb_get_prop("telephony.active_modems.max_count"),
        adb_shell_cmd("service call iphonesubinfo 1 2>/dev/null | grep -oP \"'[^']+\" | tr -d \".' \" 2>/dev/null || echo ''"),
        adb_shell_cmd("settings get global euicc_provisioned 2>/dev/null || echo ''"),
        adb_shell_cmd("dumpsys display | grep -i 'refreshrate\\|fps' | head -3 2>/dev/null || echo ''"),
    )

    info.model = props[0] or "Unknown"
    info.manufacturer = props[1] or "Unknown"
    info.brand = (props[2] or "Unknown").title()
    info.codename = props[3] or "Unknown"
    info.chipset = props[4] or props[5] or "Unknown"
    info.soc = props[5] or "Unknown"
    info.cpu_arch = props[6] or "Unknown"
    info.android_version = props[7] or "Unknown"
    info.sdk_level = props[8] or "Unknown"
    info.security_patch = props[9] or "Unknown"
    info.build_number = props[10] or "Unknown"

    # Memory
    if props[11]:
        info.ram_total, info.ram_available = _parse_meminfo(props[11])

    # Storage
    if props[12]:
        info.storage_total, info.storage_used, info.storage_free = _parse_storage(props[12])

    # Battery
    if props[13]:
        bat = _parse_battery(props[13])
        info.battery_level = bat.get("level", "")
        info.battery_health = bat.get("health", "")
        info.battery_temp = bat.get("temp", "")
        info.charging_status = bat.get("charging", "")

    # Display
    if props[14]:
        match = re.search(r"(\d+x\d+)", props[14])
        info.screen_resolution = match.group(1) if match else ""
    if props[15]:
        match = re.search(r"(\d+)", props[15])
        info.screen_dpi = match.group(1) if match else ""

    # Kernel
    info.kernel_version = props[17] or ""

    # SIM
    info.sim_provider = props[18] or props[19] or "Unknown"
    info.sim_operator = props[19] or info.sim_provider

    sim_state = props[20] or ""
    if "READY" in sim_state.upper():
        info.sim_slots = "Active"
    elif "ABSENT" in sim_state.upper():
        info.sim_slots = "No SIM"
    else:
        info.sim_slots = sim_state or "Unknown"

    # CPU
    info.cpu_cores = props[21] or ""
    if props[22]:
        try:
            freq_mhz = int(props[22]) / 1000
            info.cpu_freq = f"{freq_mhz:.0f} MHz"
        except ValueError:
            info.cpu_freq = ""

    # SIM slots count
    max_modems = props[23] or ""
    if max_modems:
        info.sim_slots = f"{max_modems} slot(s) — {info.sim_slots}"

    # IMEI
    imei_raw = props[24] or ""
    # Clean up IMEI from service call output
    cleaned = re.sub(r"[^0-9]", "", imei_raw)
    if len(cleaned) >= 14:
        info.imei = cleaned[:15]
    else:
        info.imei = "Requires root"

    # eSIM
    esim_raw = props[25] or ""
    if esim_raw.strip() == "1":
        info.esim_support = "✓ Supported"
    elif esim_raw.strip() == "0":
        info.esim_support = "✗ Not Supported"
    else:
        info.esim_support = "Unknown"

    # Refresh rate
    refresh_raw = props[26] or ""
    match = re.search(r"(\d+\.?\d*)\s*(?:fps|Hz)", refresh_raw, re.IGNORECASE)
    if match:
        info.screen_refresh_rate = f"{match.group(1)} Hz"
    else:
        info.screen_refresh_rate = ""

    info.connection_type = "USB"

    return info


# ── Experimental: Download ROM ───────────────────────────────────────

async def download_file(url: str, save_dir: str = ".", use_curl: bool = False) -> CmdResult:
    """Download a file via wget or curl."""
    if use_curl:
        # curl -L -O follows redirects, -# shows progress bar
        filename = url.rstrip("/").rsplit("/", 1)[-1] or "download"
        save_path = os.path.join(save_dir, filename)
        cmd = ["curl", "-L", "-o", save_path, url]
    else:
        cmd = ["wget", "-P", save_dir, url]

    return await run_cmd(cmd, timeout=1800.0)


# ── Experimental: ROM file management ────────────────────────────────

ROM_DIR_NAME = "zdb_rom"


@dataclass
class RomFileInfo:
    name: str = ""
    path: str = ""
    size_bytes: int = 0
    size_human: str = ""
    archive_type: str = ""  # zip, tar, tar.gz, tar.xz, xz, unknown


def get_rom_dir() -> str:
    """Return the ROM directory path (~/<user>/zdb_rom), creating it if needed."""
    home = os.path.expanduser("~")
    rom_dir = os.path.join(home, ROM_DIR_NAME)
    os.makedirs(rom_dir, exist_ok=True)
    return rom_dir


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


def _detect_archive_type(filename: str) -> str:
    """Detect archive type from filename extension."""
    lower = filename.lower()
    if lower.endswith(".zip"):
        return "zip"
    elif lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "tar.gz"
    elif lower.endswith(".tar.xz") or lower.endswith(".txz"):
        return "tar.xz"
    elif lower.endswith(".tar.bz2") or lower.endswith(".tbz2"):
        return "tar.bz2"
    elif lower.endswith(".tar"):
        return "tar"
    elif lower.endswith(".xz"):
        return "xz"
    elif lower.endswith(".gz"):
        return "gz"
    elif lower.endswith(".bz2"):
        return "bz2"
    elif lower.endswith(".7z"):
        return "7z"
    elif lower.endswith(".rar"):
        return "rar"
    return "unknown"


def list_rom_files() -> list[RomFileInfo]:
    """List all files in the ROM directory with metadata."""
    rom_dir = get_rom_dir()
    files: list[RomFileInfo] = []

    try:
        for entry in sorted(os.listdir(rom_dir)):
            full_path = os.path.join(rom_dir, entry)
            if os.path.isfile(full_path):
                stat = os.stat(full_path)
                files.append(RomFileInfo(
                    name=entry,
                    path=full_path,
                    size_bytes=stat.st_size,
                    size_human=_human_size(stat.st_size),
                    archive_type=_detect_archive_type(entry),
                ))
    except OSError:
        pass

    return files


async def extract_rom(file_path: str, output_dir: str = "") -> CmdResult:
    """Extract a ROM archive file to the specified output directory.

    Supports: .zip, .tar, .tar.gz/.tgz, .tar.xz/.txz, .tar.bz2, .xz, .gz, .bz2, .7z, .rar
    """
    if not output_dir:
        output_dir = get_rom_dir()

    if not os.path.isfile(file_path):
        return CmdResult(
            status=CmdStatus.FAILED,
            stderr=f"File not found: {file_path}",
        )

    archive_type = _detect_archive_type(os.path.basename(file_path))

    if archive_type == "zip":
        cmd = ["unzip", "-o", file_path, "-d", output_dir]
    elif archive_type == "tar":
        cmd = ["tar", "-xf", file_path, "-C", output_dir]
    elif archive_type == "tar.gz":
        cmd = ["tar", "-xzf", file_path, "-C", output_dir]
    elif archive_type == "tar.xz":
        cmd = ["tar", "-xJf", file_path, "-C", output_dir]
    elif archive_type == "tar.bz2":
        cmd = ["tar", "-xjf", file_path, "-C", output_dir]
    elif archive_type == "xz":
        # xz decompresses in-place by default; copy first then decompress
        base = os.path.basename(file_path)
        dest = os.path.join(output_dir, base)
        if dest != file_path:
            import shutil as _shutil
            _shutil.copy2(file_path, dest)
        cmd = ["xz", "-d", "-f", dest]
    elif archive_type == "gz":
        base = os.path.basename(file_path)
        dest = os.path.join(output_dir, base)
        if dest != file_path:
            import shutil as _shutil
            _shutil.copy2(file_path, dest)
        cmd = ["gzip", "-d", "-f", dest]
    elif archive_type == "bz2":
        base = os.path.basename(file_path)
        dest = os.path.join(output_dir, base)
        if dest != file_path:
            import shutil as _shutil
            _shutil.copy2(file_path, dest)
        cmd = ["bzip2", "-d", "-f", dest]
    elif archive_type == "7z":
        cmd = ["7z", "x", file_path, f"-o{output_dir}", "-y"]
    elif archive_type == "rar":
        cmd = ["unrar", "x", "-o+", file_path, output_dir + "/"]
    else:
        return CmdResult(
            status=CmdStatus.FAILED,
            stderr=f"Unsupported archive format: {os.path.basename(file_path)}",
        )

    os.makedirs(output_dir, exist_ok=True)
    return await run_cmd(cmd, timeout=1800.0)


# ── Experimental: Device switching ───────────────────────────────────

@dataclass
class ConnectedDevice:
    serial: str = ""
    status: str = ""
    model: str = ""
    transport: str = ""


async def get_connected_devices() -> list[ConnectedDevice]:
    """Parse `adb devices -l` and return structured device list."""
    result = await adb_devices()
    devices: list[ConnectedDevice] = []
    if result.status != CmdStatus.SUCCESS:
        return devices

    for line in result.stdout.strip().splitlines():
        if not line or line.startswith("List"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue

        dev = ConnectedDevice(serial=parts[0], status=parts[1])
        # Parse key:value pairs like model:Pixel_7
        for part in parts[2:]:
            if part.startswith("model:"):
                dev.model = part.split(":", 1)[1]
            elif part.startswith("transport_id:"):
                dev.transport = part.split(":", 1)[1]
        devices.append(dev)

    return devices


def set_target_device(serial: str) -> None:
    """Set the target ADB device by serial number."""
    global _target_serial
    _target_serial = serial
    os.environ["ANDROID_SERIAL"] = serial


def get_target_device() -> str:
    """Return the currently targeted device serial."""
    return _target_serial or os.environ.get("ANDROID_SERIAL", "")


# ── Experimental: Tool version checker ───────────────────────────────

@dataclass
class ToolVersionInfo:
    name: str = ""
    installed_version: str = ""
    latest_version: str = ""
    path: str = ""
    is_installed: bool = False
    is_uptodate: bool | None = None  # None = unknown


async def _get_tool_version(tool: str) -> tuple[str, str]:
    """Get version string and path for a tool. Returns (version, path)."""
    # Try which/command -v first
    which_result = await run_cmd(["which", tool], timeout=5.0)
    tool_path = which_result.stdout.strip() if which_result.status == CmdStatus.SUCCESS else ""

    version_str = ""
    if tool == "adb":
        r = await run_cmd(["adb", "version"], timeout=5.0)
        if r.status == CmdStatus.SUCCESS:
            # "Android Debug Bridge version X.X.XX\nVersion XX.X.X-XXXXXXX\n..."
            for line in r.stdout.splitlines():
                if "Version" in line and "-" in line:
                    version_str = line.split("Version", 1)[1].strip()
                    break
                elif "version" in line.lower():
                    m = re.search(r"(\d+\.\d+\.\d+)", line)
                    if m:
                        version_str = m.group(1)

    elif tool == "fastboot":
        r = await run_cmd(["fastboot", "--version"], timeout=5.0)
        if r.status == CmdStatus.SUCCESS:
            for line in r.stdout.splitlines():
                if "version" in line.lower() or "fastboot" in line.lower():
                    m = re.search(r"(\d+\.\d+[\.\d]*-?\d*)", line)
                    if m:
                        version_str = m.group(1)
                        break

    elif tool == "wget":
        r = await run_cmd(["wget", "--version"], timeout=5.0)
        if r.status == CmdStatus.SUCCESS:
            # "GNU Wget 1.21.4 built on ..."
            m = re.search(r"Wget\s+(\d+\.\d+[\.\d]*)", r.stdout)
            if m:
                version_str = m.group(1)

    elif tool == "curl":
        r = await run_cmd(["curl", "--version"], timeout=5.0)
        if r.status == CmdStatus.SUCCESS:
            # "curl 8.5.0 (x86_64-pc-linux-gnu) ..."
            m = re.search(r"curl\s+(\d+\.\d+[\.\d]*)", r.stdout)
            if m:
                version_str = m.group(1)

    elif tool == "python3":
        r = await run_cmd(["python3", "--version"], timeout=5.0)
        if r.status == CmdStatus.SUCCESS:
            m = re.search(r"(\d+\.\d+[\.\d]*)", r.stdout)
            if m:
                version_str = m.group(1)

    elif tool == "java":
        r = await run_cmd(["java", "-version"], timeout=5.0)
        out = r.stderr or r.stdout  # java prints to stderr
        m = re.search(r'"(\d+[\.\d_]*)"', out)
        if m:
            version_str = m.group(1)

    return version_str, tool_path


async def _fetch_latest_platform_tools_version() -> str:
    """Try to fetch the latest platform-tools version from Google."""
    try:
        r = await run_cmd(
            ["curl", "-sL", "--max-time", "10",
             "https://dl.google.com/android/repository/repository2-3.xml"],
            timeout=15.0,
        )
        if r.status == CmdStatus.SUCCESS and r.stdout:
            # Look for platform-tools revision in XML
            # <remotePackage path="platform-tools"> ... <revision><major>35</major><minor>0</minor><micro>2</micro>
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(r.stdout)
                ns = {"sdk": "http://schemas.android.com/sdk/android/repo/repository2/03"}
                for pkg in root.findall(".//sdk:remotePackage", ns):
                    if pkg.get("path") == "platform-tools":
                        rev = pkg.find("sdk:revision", ns)
                        if rev is not None:
                            major = rev.findtext("sdk:major", "", ns)
                            minor = rev.findtext("sdk:minor", "", ns)
                            micro = rev.findtext("sdk:micro", "", ns)
                            return f"{major}.{minor}.{micro}"
            except ET.ParseError:
                pass
            # Fallback: try regex on raw XML
            m = re.search(
                r'path="platform-tools".*?<major>(\d+)</major>.*?<minor>(\d+)</minor>.*?<micro>(\d+)</micro>',
                r.stdout, re.DOTALL,
            )
            if m:
                return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    except Exception:
        pass
    return ""


def _compare_versions(installed: str, latest: str) -> bool | None:
    """Compare version strings. Returns True if up to date, False if not, None if unknown."""
    if not installed or not latest:
        return None
    try:
        # Strip any suffix after hyphen (e.g. "35.0.2-12345678")
        inst_base = installed.split("-")[0]
        lat_base = latest.split("-")[0]
        inst_parts = [int(x) for x in inst_base.split(".")]
        lat_parts = [int(x) for x in lat_base.split(".")]
        # Pad to same length
        max_len = max(len(inst_parts), len(lat_parts))
        inst_parts.extend([0] * (max_len - len(inst_parts)))
        lat_parts.extend([0] * (max_len - len(lat_parts)))
        return inst_parts >= lat_parts
    except (ValueError, IndexError):
        return None


async def check_tool_versions() -> list[ToolVersionInfo]:
    """Check installed versions of all relevant tools and compare with latest."""
    tools = ["adb", "fastboot", "wget", "curl", "python3", "java"]

    # Get all local versions concurrently
    version_tasks = [_get_tool_version(t) for t in tools]
    results = await asyncio.gather(*version_tasks, return_exceptions=True)

    # Fetch latest platform-tools version (for adb/fastboot)
    latest_pt = await _fetch_latest_platform_tools_version()

    infos: list[ToolVersionInfo] = []
    for tool, result in zip(tools, results):
        info = ToolVersionInfo(name=tool)
        if isinstance(result, Exception):
            info.is_installed = False
        else:
            ver, path = result
            info.installed_version = ver
            info.path = path
            info.is_installed = bool(ver)

            # Compare with latest for adb/fastboot
            if tool in ("adb", "fastboot") and latest_pt:
                info.latest_version = latest_pt
                info.is_uptodate = _compare_versions(ver, latest_pt)

        infos.append(info)

    return infos


# ── Experimental: zdb Update Checker ─────────────────────────────────

@dataclass
class ZdbUpdateInfo:
    latest_version: str = ""
    changelog: str = ""
    download_url: str = ""
    error: str = ""
    is_newer: bool = False


async def check_zdb_update(current_version: str) -> ZdbUpdateInfo:
    """Fetch update information from the zdb API endpoint using curl."""
    api_url = "https://nc4tt.github.io/api/zdb_v1"
    info = ZdbUpdateInfo()

    r = await run_cmd(
        ["curl", "-sL", "--max-time", "10", api_url],
        timeout=15.0,
    )

    if r.status != CmdStatus.SUCCESS or not r.stdout.strip():
        info.error = f"Failed to fetch updates from API: {r.stderr or 'No response'}"
        return info

    try:
        data = json.loads(r.stdout)
        info.latest_version = data.get("version", "").strip()
        info.changelog = data.get("changelog", "").strip()
        info.download_url = data.get("url", "").strip()

        if info.latest_version:
            # Re-use the _compare_versions logic. False means installed is NOT >= latest,
            # so True if current_version < latest_version.
            cmp_result = _compare_versions(current_version, info.latest_version)
            if cmp_result is False:
                info.is_newer = True

    except json.JSONDecodeError:
        info.error = "Failed to parse API response (invalid JSON payload)."
    except Exception as e:
        info.error = f"Unknown error checking for updates: {e}"

    return info


# ── Experimental: Install dependencies ───────────────────────────────

@dataclass
class DistroInfo:
    name: str = ""
    family: str = ""       # debian, rhel, suse, arch, alpine, void, gentoo, nix, unknown
    pkg_manager: str = ""  # apt, dnf, yum, zypper, pacman, apk, xbps, emerge, nix-env
    version: str = ""


def detect_distro() -> DistroInfo:
    """Detect the current Linux distribution from /etc/os-release."""
    info = DistroInfo()
    try:
        with open("/etc/os-release") as f:
            data: dict[str, str] = {}
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, _, val = line.partition("=")
                    data[key] = val.strip('"').strip("'")

            info.name = data.get("PRETTY_NAME", data.get("NAME", "Unknown"))
            info.version = data.get("VERSION_ID", "")
            id_val = data.get("ID", "").lower()
            id_like = data.get("ID_LIKE", "").lower()

            # Determine family and package manager
            if id_val in ("ubuntu", "debian", "linuxmint", "pop", "elementary",
                          "zorin", "kali", "raspbian", "deepin", "mx"):
                info.family = "debian"
                info.pkg_manager = "apt"
            elif "debian" in id_like or "ubuntu" in id_like:
                info.family = "debian"
                info.pkg_manager = "apt"
            elif id_val in ("fedora", "rhel", "centos", "rocky", "alma",
                            "oracle", "nobara", "ultramarine"):
                info.family = "rhel"
                info.pkg_manager = "dnf"
            elif "fedora" in id_like or "rhel" in id_like or "centos" in id_like:
                info.family = "rhel"
                # Older RHEL/CentOS may use yum
                info.pkg_manager = "dnf" if shutil.which("dnf") else "yum"
            elif id_val in ("opensuse-tumbleweed", "opensuse-leap", "sles", "opensuse"):
                info.family = "suse"
                info.pkg_manager = "zypper"
            elif "suse" in id_like:
                info.family = "suse"
                info.pkg_manager = "zypper"
            elif id_val in ("arch", "manjaro", "endeavouros", "garuda",
                            "artix", "cachyos", "arcolinux"):
                info.family = "arch"
                info.pkg_manager = "pacman"
            elif "arch" in id_like:
                info.family = "arch"
                info.pkg_manager = "pacman"
            elif id_val == "alpine":
                info.family = "alpine"
                info.pkg_manager = "apk"
            elif id_val == "void":
                info.family = "void"
                info.pkg_manager = "xbps-install"
            elif id_val == "gentoo":
                info.family = "gentoo"
                info.pkg_manager = "emerge"
            elif id_val == "nixos":
                info.family = "nix"
                info.pkg_manager = "nix-env"
            else:
                info.family = "unknown"
                # Try to detect pkg manager from available commands
                for pm in ("apt", "dnf", "yum", "zypper", "pacman", "apk",
                           "xbps-install", "emerge", "nix-env"):
                    if shutil.which(pm):
                        info.pkg_manager = pm
                        break
    except FileNotFoundError:
        info.name = "Unknown Linux"
        info.family = "unknown"

    return info


# Package name mapping per family
_PKG_MAP: dict[str, dict[str, list[str]]] = {
    "debian":  {"adb": ["adb"], "fastboot": ["fastboot"],
                "wget": ["wget"], "curl": ["curl"]},
    "rhel":    {"adb": ["android-tools"], "fastboot": ["android-tools"],
                "wget": ["wget"], "curl": ["curl"]},
    "suse":    {"adb": ["android-tools"], "fastboot": ["android-tools"],
                "wget": ["wget"], "curl": ["curl"]},
    "arch":    {"adb": ["android-tools"], "fastboot": ["android-tools"],
                "wget": ["wget"], "curl": ["curl"]},
    "alpine":  {"adb": ["android-tools"], "fastboot": ["android-tools"],
                "wget": ["wget"], "curl": ["curl"]},
    "void":    {"adb": ["android-tools"], "fastboot": ["android-tools"],
                "wget": ["wget"], "curl": ["curl"]},
    "gentoo":  {"adb": ["dev-util/android-tools"], "fastboot": ["dev-util/android-tools"],
                "wget": ["net-misc/wget"], "curl": ["net-misc/curl"]},
    "nix":     {"adb": ["android-tools"], "fastboot": ["android-tools"],
                "wget": ["wget"], "curl": ["curl"]},
}

# Install command templates per package manager
_INSTALL_CMD: dict[str, list[str]] = {
    "apt":          ["sudo", "apt", "install", "-y"],
    "dnf":          ["sudo", "dnf", "install", "-y"],
    "yum":          ["sudo", "yum", "install", "-y"],
    "zypper":       ["sudo", "zypper", "install", "-y"],
    "pacman":       ["sudo", "pacman", "-S", "--noconfirm"],
    "apk":          ["sudo", "apk", "add"],
    "xbps-install": ["sudo", "xbps-install", "-y"],
    "emerge":       ["sudo", "emerge", "--ask=n"],
    "nix-env":      ["nix-env", "-iA", "nixpkgs."],  # special handling
}


def get_install_command(distro: DistroInfo, packages: list[str]) -> tuple[list[str], str]:
    """Build the install command for the given distro and packages.

    Returns (command_list, human_readable_string).
    """
    family = distro.family
    pm = distro.pkg_manager

    # Resolve package names for this family
    pkg_map = _PKG_MAP.get(family, _PKG_MAP.get("debian", {}))
    resolved: list[str] = []
    seen: set[str] = set()
    for pkg in packages:
        names = pkg_map.get(pkg, [pkg])
        for n in names:
            if n not in seen:
                resolved.append(n)
                seen.add(n)

    if pm == "nix-env":
        # nix-env uses a different syntax
        cmd = ["nix-env", "-iA"] + [f"nixpkgs.{p}" for p in resolved]
    else:
        base = _INSTALL_CMD.get(pm, ["sudo", pm, "install", "-y"])
        cmd = base + resolved

    human = " ".join(cmd)
    return cmd, human


async def install_dependencies(
    packages: list[str] | None = None,
    password: str = "",
) -> tuple[DistroInfo, CmdResult]:
    """Detect distro and install the specified packages (default: adb, fastboot, wget, curl)."""
    if packages is None:
        packages = ["adb", "fastboot", "wget", "curl"]

    distro = detect_distro()
    if not distro.pkg_manager:
        result = CmdResult(
            status=CmdStatus.FAILED,
            stderr="Could not detect package manager. Please install manually.",
        )
        return distro, result

    cmd, _ = get_install_command(distro, packages)

    if password:
        result = await run_cmd_sudo(cmd, password, timeout=600.0)
    else:
        result = await run_cmd(cmd, timeout=600.0)

    return distro, result


# ── API Frontend & Backend OOP Wrapper ───────────────────────────────

class ZDBBackend:
    """Singleton object-oriented wrapper for the ZDB API.
    
    This provides a highly extensible and modular way to consume the backend functions.
    """
    
    _instance = None

    def __new__(cls) -> "ZDBBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __getattr__(self, name: str):
        # Map aliases for convenience and backwards compatibility
        if name == "get_adb_devices":
            name = "get_connected_devices"
            
        func = globals().get(name)
        if callable(func):
            return func
        raise AttributeError(f"'ZDBBackend' object has no attribute '{name}'")
        
    async def execute_cmd(self, action: str, *args, **kwargs):
        """Execute a specific backend command dynamically.
        Used primarily for flexible TUI routing.
        """
        if action == "rom_extract":
            action = "extract_rom"
        
        # We fetch the actual backend function
        func = getattr(self, action)
        return await func(*args, **kwargs)

