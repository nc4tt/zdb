"""
zdb — Main application entry point.

A premium terminal interface for managing Android devices
via ADB and Fastboot with smooth animations and live status.

Usage:
    python -m zdb.app
    # or after pip install -e .:
    zdb
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from zdb.screens.splash import SplashScreen


class ZdbApp(App):
    """zdb — Premium Terminal Interface for ADB & Fastboot."""

    TITLE = "zdb"
    SUB_TITLE = "Android Debug Bridge & Fastboot"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        """Show the splash screen on startup."""
        self.push_screen(SplashScreen())


def main() -> None:
    app = ZdbApp()
    app.run()

    # ── Farewell message after app closes ──
    CYAN = "\033[38;2;79;195;247m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    GREY = "\033[38;2;139;148;158m"

    print()
    print(f"{CYAN}{BOLD}  ⬡ zdb — Session Ended{RESET}")
    print(f"{GREY}  ─────────────────────────────────────{RESET}")
    print(f"{GREY}  Thank you for using zdb.{RESET}")
    print(f"{DIM}  Run {CYAN}zdb{RESET}{DIM} to start again.{RESET}")
    print()


if __name__ == "__main__":
    main()
