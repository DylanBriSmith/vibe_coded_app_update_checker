"""Custom widgets for the TUI."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from ..models import App, AppStatus, AppSource

if TYPE_CHECKING:
    from .app import UpdateCheckerApp


class AppTable(DataTable):
    """DataTable for displaying apps."""

    BINDINGS = [
        ("enter", "select_cursor", "Select"),
        ("i", "toggle_ignore", "Ignore"),
        ("d", "delete", "Delete"),
        ("o", "open_url", "Open URL"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.apps: list[App] = []

    def on_mount(self) -> None:
        self.table = self
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.show_cursor = True

    def update_apps(self, apps: list[App]) -> None:
        """Update the table with new app data."""
        self.apps = apps
        self.clear(columns=True)

        self.add_column("Name", width=30)
        self.add_column("Installed", width=15)
        self.add_column("Latest", width=15)
        self.add_column("Source", width=10)
        self.add_column("Status", width=12)

        for app in apps:
            status_text = self._get_status_text(app)
            source_text = app.source.value.upper()

            self.add_row(
                app.name,
                app.installed_version or "Unknown",
                app.latest_version or "Unknown",
                source_text,
                status_text,
                key=app.id,
            )

    def _get_status_text(self, app: App) -> Text:
        """Get status text for an app."""
        status = app.status

        if status == AppStatus.OK:
            return Text("OK", style="green")
        elif status == AppStatus.UPDATE_AVAILABLE:
            return Text("UPDATE", style="yellow bold")
        elif status == AppStatus.CHECKING:
            return Text("CHECKING...", style="cyan")
        elif status == AppStatus.ERROR:
            return Text("ERROR", style="red")
        elif status == AppStatus.IGNORED:
            return Text("IGNORED", style="dim")
        else:
            return Text("UNKNOWN", style="magenta")

    def get_selected_app(self) -> App | None:
        """Get the currently selected app."""
        if self.cursor_row is None or not self.apps:
            return None

        if 0 <= self.cursor_row < len(self.apps):
            return self.apps[self.cursor_row]
        return None

    class AppSelected(Message):
        """Message sent when an app is selected."""

        def __init__(self, app: App) -> None:
            self.app = app
            super().__init__()

    class ToggleIgnore(Message):
        """Message sent when ignore should be toggled."""

        def __init__(self, app: App) -> None:
            self.app = app
            super().__init__()

    class DeleteApp(Message):
        """Message sent when app should be deleted."""

        def __init__(self, app: App) -> None:
            self.app = app
            super().__init__()

    class OpenUrl(Message):
        """Message sent when URL should be opened."""

        def __init__(self, app: App) -> None:
            self.app = app
            super().__init__()

    def action_toggle_ignore(self) -> None:
        app = self.get_selected_app()
        if app:
            self.post_message(self.ToggleIgnore(app))

    def action_delete(self) -> None:
        app = self.get_selected_app()
        if app:
            self.post_message(self.DeleteApp(app))

    def action_open_url(self) -> None:
        app = self.get_selected_app()
        if app:
            self.post_message(self.OpenUrl(app))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        app = self.get_selected_app()
        if app:
            self.post_message(self.AppSelected(app))


class StatusBar(Static):
    """Status bar widget."""

    total_apps = reactive(0)
    updates_available = reactive(0)
    last_scan = reactive("Never")

    def watch_total_apps(self, count: int) -> None:
        self._update_text()

    def watch_updates_available(self, count: int) -> None:
        self._update_text()

    def watch_last_scan(self, time: str) -> None:
        self._update_text()

    def _update_text(self) -> None:
        updates_style = "yellow bold" if self.updates_available > 0 else "green"
        self.update(
            f"Apps: {self.total_apps} | "
            f"Updates: [{updates_style}]{self.updates_available}[/{updates_style}] | "
            f"Last scan: {self.last_scan}"
        )


class AppDetail(Widget):
    """Widget to display app details."""

    tracked_app: App | None = None

    def __init__(self, tracked_app: App | None = None, **kwargs):
        super().__init__(**kwargs)
        self.tracked_app = tracked_app

    def compose(self) -> ComposeResult:
        if self.tracked_app:
            yield self._build_detail_content()
        else:
            yield Label("No app selected", classes="detail-empty")

    def _build_detail_content(self) -> Container:
        if not self.tracked_app:
            return Container(Label("No app"))

        lines = [
            f"[bold]{self.tracked_app.name}[/bold]",
            "",
            f"Source: {self.tracked_app.source.value.upper()}",
            f"Installed: {self.tracked_app.installed_version or 'Unknown'}",
            f"Latest: {self.tracked_app.latest_version or 'Unknown'}",
            f"Status: {self._get_status_display()}",
            "",
        ]

        if self.tracked_app.source == AppSource.WINGET:
            lines.append(f"Winget ID: {self.tracked_app.winget_id}")
        elif self.tracked_app.source == AppSource.GITHUB:
            lines.append(f"GitHub Repo: {self.tracked_app.github_repo}")
        elif self.tracked_app.source == AppSource.CUSTOM:
            lines.append(f"Custom URL: {self.tracked_app.custom_url}")
            if self.tracked_app.version_regex:
                lines.append(f"Version Regex: {self.tracked_app.version_regex}")

        if self.tracked_app.release_url:
            lines.append("")
            lines.append(f"Release URL: {self.tracked_app.release_url}")

        if self.tracked_app.last_error:
            lines.append("")
            lines.append(f"[red]Error: {self.tracked_app.last_error}[/red]")

        return Container(
            Static("\n".join(lines), classes="detail-content"),
            classes="detail-panel",
        )

    def _get_status_display(self) -> str:
        if not self.tracked_app:
            return "Unknown"

        status = self.tracked_app.status
        if status == AppStatus.OK:
            return "[green]Up to date[/green]"
        elif status == AppStatus.UPDATE_AVAILABLE:
            return "[yellow]Update available[/yellow]"
        elif status == AppStatus.IGNORED:
            return "[dim]Ignored[/dim]"
        elif status == AppStatus.ERROR:
            return "[red]Error[/red]"
        else:
            return "[magenta]Unknown[/magenta]"

    def update_app(self, app: Optional[App]) -> None:
        self.tracked_app = app
        self.refresh(recompose=True)