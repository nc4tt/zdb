"""ASCII art assets for the TUI application."""

LOGO = r"""
            ____  
 ____  ____/ / /_ 
/_  / / __  / __ \
 / /_/ /_/ / /_/ /
/___/\__,_/_.___/ """

DEVICE_ART = r"""
    ┌─────────────────────┐
    │  ╭───────────────╮  │
    │  │               │  │
    │  │               │  │
    │  │               │  │
    │  │    ┌─────┐    │  │
    │  │    │ ◉◉◉ │    │  │
    │  │    └─────┘    │  │
    │  │               │  │
    │  │               │  │
    │  │               │  │
    │  ╰───────────────╯  │
    │        ╭───╮        │
    │        │   │        │
    │        ╰───╯        │
    └─────────────────────┘"""

LOADING_FRAMES = [
    "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
]

BOOT_SEQUENCE = [
    "█ Bootstrapping zdb v6...",
    "█ Loading core modules...",
    "█ Enumerating USB devices...",
    "█ Connecting to ADB daemon...",
    "█ System ready ✓",
]
