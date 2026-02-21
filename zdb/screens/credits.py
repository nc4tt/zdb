"""Credits screen — contributor acknowledgements."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static


# ── Credits data ─────────────────────────────────────────────────

CREDITS = [
    ("realncatt", "Setup all interfaces, UI/UX design"),
    ("python3", "Modules, core libraries & scripting"),
    ("Textual", "TUI framework powering the interface"),
    ("Rich", "Rich text rendering & formatting"),
    ("Google", "ADB & Fastboot platform tools"),
]


# ── Credits screen ───────────────────────────────────────────────


class CreditsScreen(Screen):
    """Scrollable credits listing all contributors."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("backspace", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="op-screen"):
            with Container(classes="op-header"):
                yield Static(
                    "👥 Credits  —  [bold #484f58]ESC[/] Back",
                    classes="op-header-title",
                )
                yield Button(
                    "✕ Close",
                    id="btn-close-screen",
                    classes="header-close-btn",
                )

            with Vertical(id="credits-body"):
                yield Static(
                    "[bold #4fc3f7]Thank you to everyone who made zdb possible![/]",
                    classes="credits-heading",
                )
                for name, role in CREDITS:
                    with Container(classes="credit-card"):
                        yield Static(
                            f"[bold #4fc3f7]⬡[/]  [bold #e6edf3]{name}[/]",
                            classes="credit-name",
                        )
                        yield Static(
                            f"  [#8b949e]{role}[/]",
                            classes="credit-role",
                        )

    async def on_mount(self) -> None:
        """Fade in credit cards."""
        cards = self.query(".credit-card")
        for card in cards:
            card.styles.opacity = 0.0
        for i, card in enumerate(cards):
            self.set_timer(0.15 * (i + 1), lambda w=card: self._fade_in(w))

    def _fade_in(self, widget) -> None:
        widget.styles.animate("opacity", value=1.0, duration=0.4)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-screen":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
