<div align="center">

# zdb - Premium Terminal Interface for ADB & Fastboot

**A modern, visually stunning, and highly functional Terminal User Interface (TUI) for Android device management.**

</div>

## 🌟 Overview

**zdb** is a premium TUI application built with [Textual](https://textual.textualize.io/) and [Rich](https://rich.readthedocs.io/), designed to elevate the experience of using Android Debug Bridge (ADB) and Fastboot. With smooth animations, live status indicators, a Material-inspired dark theme, and comprehensive functionality, zdb brings modern GUI convenience and power right into your terminal.

## ✨ Features

- **📱 Comprehensive ADB Support:**
  - Execute standard ADB shell commands.
  - Push and Pull files to and from your device effortlessly.
  - Install/Uninstall APKs.
  - Live, colorized Logcat viewer.
  - Device reboot options (System, Recovery, Bootloader/Fastboot, EDL).

- **⚡ Advanced Fastboot Management:**
  - Complete control over fastboot operations.
  - Flash device partitions seamlessly.
  - Get granular device information (product, serial no, bootloader status).
  - Manage Active Slots (`set_active a` or `b`).
  - Partition Management (Create/Delete logical partitions).
  - Lock & Unlock bootloader.
  - Send OEM commands directly.

- **ℹ️ Detailed Device Information:**
  - View real-time hardware specifications.
  - Explore deeply integrated SIM details and network status.
  - High-quality, dynamically fetched model images and visual specs representation.

- **🛠️ Experimental ROM Features:**
  - **ROM Management:** Detect, manage, and extract ROM archives (supports zip, tar, gz, xz, 7z, and more).
  - Verify ROM integrity and view detailed metadata (name, size, type).
  - Built-in zdb update checker to keep you running the latest version.

- **🎨 Premium User Experience:**
  - Smooth TUI scrolling, interactive dialogs, and dynamic layout.
  - Status indicators (Running, Failed, Auth Required).
  - Custom boot splash and animated intro graphics.

## 🚀 Installation

Ensure you have Python 3.10 or higher installed, as well as the Android `adb` and `fastboot` platform tools setup.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/nc4tt/zdb
   cd zdb
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the application:**
   ```bash
   pip install -e .
   ```

## 🎮 Usage

You can start the application using the installed command or directly as a python module.

```bash
# Using the installed application binary
zdb

# Or running it via the Python module
python -m zdb.app

# Or using the local run script if available
bash zdb-run
```

Navigate through the sidebar to access different screens: **Dashboard, ADB Screen, Fastboot Screen, Device Info, Experimental**, and more. 

## 🛠️ Requirements
- Python >= 3.10
- `textual >= 0.47.0`
- `rich >= 13.0.0`
- `adb` and `fastboot` binaries installed and available in system PATH.

## 🤝 Contributing
Contributions are welcome! Please open an issue or submit a pull request for any new features, fastboot command expansions, UI tweaks, or bug fixes.
