"""TUI Screens for App Update Checker."""

import asyncio
import webbrowser
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RadioSet,
    RadioButton,
    Static,
)

from ..models import App, AppSource, AppStatus
from ..utils import add_app, delete_app, load_apps, save_apps, update_app
from .widgets import AppTable, AppDetail, StatusBar

if TYPE_CHECKING:
    from .app import UpdateCheckerApp


class MainScreen(Screen):
    """Main screen with app table."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("a", "add_app", "Add App"),
        ("s", "scan_apps", "Scan"),
        ("/", "search", "Search"),
        ("escape", "clear_search", "Clear"),
    ]

    apps: reactive[list[App]] = reactive([])
    is_checking: reactive[bool] = reactive(False)
    search_query: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="main-container"):
            yield Input(placeholder="Search apps... (press / to focus)", id="search-input")
            yield AppTable(id="app-table")
            with Container(classes="right-panel"):
                yield AppDetail(id="app-detail")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._load_apps()
        self._update_status_bar()

    def _load_apps(self) -> None:
        """Load apps from storage."""
        self.apps = load_apps()
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the app table with optional search filter."""
        table = self.query_one("#app-table", AppTable)
        if self.search_query:
            filtered = [a for a in self.apps if self.search_query.lower() in a.name.lower()]
            table.update_apps(filtered)
        else:
            table.update_apps(self.apps)

    def _update_status_bar(self) -> None:
        """Update the status bar."""
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.total_apps = len(self.apps)
        status_bar.updates_available = sum(
            1 for app in self.apps if app.status == AppStatus.UPDATE_AVAILABLE
        )
        status_bar.last_scan = datetime.now().strftime("%H:%M:%S")

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        self.search_query = event.value
        self._refresh_table()

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        """Handle search submit - focus the table."""
        table = self.query_one("#app-table", AppTable)
        table.focus()

    def action_search(self) -> None:
        """Focus search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def action_clear_search(self) -> None:
        """Clear search filter."""
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        self.search_query = ""
        self._refresh_table()

    def action_refresh(self) -> None:
        """Refresh all apps."""
        if self.is_checking:
            return

        self.is_checking = True
        self.app.call_later(self._check_all_apps)

    async def _check_all_apps(self) -> None:
        """Check all apps for updates concurrently."""
        from .app import UpdateCheckerApp
        
        checker_app = cast(UpdateCheckerApp, self.app)
        semaphore = asyncio.Semaphore(5)
        
        async def check_one(app: App, index: int) -> None:
            async with semaphore:
                self.apps[index].last_checked = datetime.now().isoformat()
                info = await checker_app.check_app(app)
                
                self.apps[index].latest_version = info.latest_version
                self.apps[index].release_url = info.release_url
                self.apps[index].last_error = info.error
                
                self._refresh_table()
        
        tasks = [
            check_one(app, i) 
            for i, app in enumerate(self.apps) 
            if not app.ignored
        ]
        
        if tasks:
            await asyncio.gather(*tasks)
        
        save_apps(self.apps)
        self.is_checking = False
        self._update_status_bar()

    def action_add_app(self) -> None:
        """Open add app screen."""
        self.app.push_screen("add-app")

    def action_scan_apps(self) -> None:
        """Open scan screen."""
        self.app.push_screen("scan")

    @on(AppTable.AppSelected)
    def on_app_selected(self, event: AppTable.AppSelected) -> None:
        """Handle app selection."""
        detail = self.query_one("#app-detail", AppDetail)
        detail.update_app(event.app)

    @on(AppTable.ToggleIgnore)
    def on_toggle_ignore(self, event: AppTable.ToggleIgnore) -> None:
        """Handle toggle ignore."""
        app = event.app
        app.ignored = not app.ignored

        for i, a in enumerate(self.apps):
            if a.id == app.id:
                self.apps[i] = app
                break

        save_apps(self.apps)
        self._refresh_table()
        self._update_status_bar()

    @on(AppTable.DeleteApp)
    def on_delete_app(self, event: AppTable.DeleteApp) -> None:
        """Handle delete app."""
        app = event.app
        self.apps = [a for a in self.apps if a.id != app.id]
        save_apps(self.apps)
        self._refresh_table()
        self._update_status_bar()

        detail = self.query_one("#app-detail", AppDetail)
        detail.update_app(None)

    @on(AppTable.OpenUrl)
    def on_open_url(self, event: AppTable.OpenUrl) -> None:
        """Handle open URL."""
        app = event.app
        if app.release_url:
            webbrowser.open(app.release_url)
        elif app.source == AppSource.GITHUB and app.github_repo:
            webbrowser.open(f"https://github.com/{app.github_repo}/releases")
        elif app.source == AppSource.CUSTOM and app.custom_url:
            webbrowser.open(app.custom_url)

    def on_screen_resume(self) -> None:
        """Called when returning from another screen."""
        self._load_apps()
        self._update_status_bar()


class AddAppScreen(ModalScreen):
    """Modal screen for adding a new app."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "submit", "Submit"),
    ]

    selected_source: reactive[str] = reactive("winget")
    is_detecting: reactive[bool] = reactive(False)
    detected_patterns: reactive[list] = reactive([])

    def compose(self) -> ComposeResult:
        with Container(classes="add-app-container"):
            yield Label("Add New App", classes="screen-title")
            
            yield Label("App Name:")
            yield Input(placeholder="e.g., DaVinci Resolve", id="app-name")
            
            yield Label("Installed Version (optional):")
            yield Input(placeholder="e.g., 1.2.3", id="installed-version")
            
            yield Label("Source Type:")
            with RadioSet(id="source-type"):
                yield RadioButton("Winget (Windows)", value=True, id="source-winget")
                yield RadioButton("GitHub Releases", id="source-github")
                yield RadioButton("Custom URL", id="source-custom")
                yield RadioButton("Homebrew (macOS)", id="source-homebrew")
            
            with Container(id="winget-options", classes="source-options"):
                yield Label("Winget ID (optional, will search if empty):")
                yield Input(placeholder="e.g., 7zip.7zip", id="winget-id")
                yield Button("Search Winget", id="search-winget", variant="primary")
            
            with Container(id="github-options", classes="source-options hidden"):
                yield Label("GitHub Repository (owner/repo):")
                yield Input(placeholder="e.g., obsidianmd/obsidian-releases", id="github-repo")
                yield Button("Validate Repository", id="validate-github", variant="primary")
            
            with Container(id="custom-options", classes="source-options hidden"):
                yield Label("Version Check URL:")
                yield Input(placeholder="https://example.com/downloads", id="custom-url")
                yield Label("Version Regex (optional):")
                yield Input(placeholder="e.g., Version (\\d+\\.\\d+)", id="version-regex")
                yield Button("Auto-Detect Version", id="auto-detect", variant="primary")
                with VerticalScroll(id="detected-patterns"):
                    yield Static("", id="detection-result")
            
            with Container(id="homebrew-options", classes="source-options hidden"):
                yield Label("Homebrew Formula:")
                yield Input(placeholder="e.g., wget or homebrew/cask/spotify", id="homebrew-formula")
                yield Button("Search Homebrew", id="search-homebrew", variant="primary")
            
            with Horizontal(classes="button-row"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Add App", id="add-btn", variant="success")

    def on_mount(self) -> None:
        self._update_source_options()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        radio_id = event.pressed.id if event.pressed else "source-winget"
        
        if radio_id == "source-winget":
            self.selected_source = "winget"
        elif radio_id == "source-github":
            self.selected_source = "github"
        elif radio_id == "source-custom":
            self.selected_source = "custom"
        elif radio_id == "source-homebrew":
            self.selected_source = "homebrew"
        
        self._update_source_options()

    def _update_source_options(self) -> None:
        """Show/hide source-specific options."""
        winget_opts = self.query_one("#winget-options")
        github_opts = self.query_one("#github-options")
        custom_opts = self.query_one("#custom-options")
        homebrew_opts = self.query_one("#homebrew-options")

        winget_opts.set_class(self.selected_source != "winget", "hidden")
        github_opts.set_class(self.selected_source != "github", "hidden")
        custom_opts.set_class(self.selected_source != "custom", "hidden")
        homebrew_opts.set_class(self.selected_source != "homebrew", "hidden")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "cancel-btn":
            self.app.pop_screen()
        elif button_id == "add-btn":
            self._add_app()
        elif button_id == "auto-detect":
            await self._auto_detect_version()
        elif button_id == "validate-github":
            await self._validate_github()
        elif button_id == "search-winget":
            await self._search_winget()
        elif button_id == "search-homebrew":
            await self._search_homebrew()

    async def _auto_detect_version(self) -> None:
        """Auto-detect version patterns from URL."""
        from .app import UpdateCheckerApp
        
        url_input = self.query_one("#custom-url", Input)
        url = url_input.value.strip()

        if not url:
            return

        result_widget = self.query_one("#detection-result", Static)
        result_widget.update("[cyan]Detecting version patterns...[/cyan]")

        checker_app = cast(UpdateCheckerApp, self.app)
        patterns = await checker_app.detect_version_patterns(url)

        if patterns:
            lines = ["[green]Detected patterns:[/green]", ""]
            for p in patterns[:5]:
                lines.append(f"• {p['pattern']}")
                lines.append(f"  Examples: {', '.join(p['examples'])}")
                lines.append("")
            result_widget.update("\n".join(lines))
            
            if patterns:
                regex_input = self.query_one("#version-regex", Input)
                regex_input.value = patterns[0]["pattern"]
        else:
            result_widget.update("[red]Could not detect version patterns[/red]")

    async def _validate_github(self) -> None:
        """Validate GitHub repository."""
        from .app import UpdateCheckerApp
        
        repo_input = self.query_one("#github-repo", Input)
        repo = repo_input.value.strip()

        if not repo:
            return

        checker_app = cast(UpdateCheckerApp, self.app)
        is_valid, error = await checker_app.validate_github_repo(repo)

        if is_valid:
            repo_input.styles.border = ("solid", "green")
        else:
            repo_input.styles.border = ("solid", "red")

    async def _search_winget(self) -> None:
        """Search winget for package."""
        from .app import UpdateCheckerApp
        
        name_input = self.query_one("#app-name", Input)
        name = name_input.value.strip()

        if not name:
            return

        winget_input = self.query_one("#winget-id", Input)
        winget_input.value = "[Searching...]"

        checker_app = cast(UpdateCheckerApp, self.app)
        results = await checker_app.search_winget(name)

        if results:
            winget_input.value = results[0].get("id", "")
        else:
            winget_input.value = ""

    async def _search_homebrew(self) -> None:
        """Search Homebrew for formula."""
        from ..checkers.homebrew import HomebrewChecker
        
        name_input = self.query_one("#app-name", Input)
        name = name_input.value.strip()

        if not name:
            return

        formula_input = self.query_one("#homebrew-formula", Input)
        formula_input.value = "[Searching...]"

        checker = HomebrewChecker()
        results = await checker.search_formula(name)

        if results:
            formula_input.value = results[0].get("homebrew_formula", "")
        else:
            formula_input.value = ""

    def _add_app(self) -> None:
        """Add the new app."""
        name_input = self.query_one("#app-name", Input)
        name = name_input.value.strip()

        if not name:
            return

        app_data: dict[str, Any] = {
            "name": name,
            "source": self.selected_source,
        }

        version_input = self.query_one("#installed-version", Input)
        installed_version = version_input.value.strip()
        if installed_version:
            app_data["installed_version"] = installed_version

        if self.selected_source == "winget":
            winget_input = self.query_one("#winget-id", Input)
            app_data["winget_id"] = winget_input.value.strip() or None  # type: ignore[misc]

        elif self.selected_source == "github":
            repo_input = self.query_one("#github-repo", Input)
            app_data["github_repo"] = repo_input.value.strip()

        elif self.selected_source == "custom":
            url_input = self.query_one("#custom-url", Input)
            regex_input = self.query_one("#version-regex", Input)
            app_data["custom_url"] = url_input.value.strip()
            app_data["version_regex"] = regex_input.value.strip() or None  # type: ignore[misc]

        elif self.selected_source == "homebrew":
            formula_input = self.query_one("#homebrew-formula", Input)
            app_data["homebrew_formula"] = formula_input.value.strip()

        app = App.from_dict(app_data)
        add_app(app)

        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()

    def action_submit(self) -> None:
        self._add_app()


class DetailScreen(ModalScreen):
    """Modal screen showing app details."""

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, app_obj: App, **kwargs):
        super().__init__(**kwargs)
        self.app_obj = app_obj

    def compose(self) -> ComposeResult:
        with Container(classes="detail-container"):
            yield Label(f"[bold]{self.app_obj.name}[/bold]", classes="screen-title")
            
            lines = [
                f"Source: {self.app_obj.source.value.upper()}",
                f"Installed Version: {self.app_obj.installed_version or 'Unknown'}",
                f"Latest Version: {self.app_obj.latest_version or 'Unknown'}",
                f"Status: {self._get_status_display()}",
                "",
            ]

            if self.app_obj.source == AppSource.WINGET:
                lines.append(f"Winget ID: {self.app_obj.winget_id}")
            elif self.app_obj.source == AppSource.GITHUB:
                lines.append(f"GitHub Repo: {self.app_obj.github_repo}")
            elif self.app_obj.source == AppSource.CUSTOM:
                lines.append(f"Custom URL: {self.app_obj.custom_url}")
                if self.app_obj.version_regex:
                    lines.append(f"Version Regex: {self.app_obj.version_regex}")

            if self.app_obj.release_url:
                lines.append(f"\nRelease URL: {self.app_obj.release_url}")

            if self.app_obj.last_error:
                lines.append(f"\n[red]Error: {self.app_obj.last_error}[/red]")

            if self.app_obj.last_checked:
                lines.append(f"\nLast Checked: {self.app_obj.last_checked}")

            yield Static("\n".join(lines), classes="detail-content")
            
            with Horizontal(classes="button-row"):
                yield Button("Close", id="close-btn", variant="default")
                yield Button("Open URL", id="open-url-btn", variant="primary")

    def _get_status_display(self) -> str:
        status = self.app_obj.status
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.app.pop_screen()
        elif event.button.id == "open-url-btn":
            if self.app_obj.release_url:
                webbrowser.open(self.app_obj.release_url)

    def action_close(self) -> None:
        self.app.pop_screen()


class ScanScreen(ModalScreen):
    """Modal screen for scanning installed apps."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    scanned_apps: reactive[list[dict]] = reactive([])
    is_scanning: reactive[bool] = reactive(False)
    selected_apps: reactive[set[int]] = reactive(set)

    def compose(self) -> ComposeResult:
        with Container(classes="scan-container"):
            yield Label("Scan Installed Applications", classes="screen-title")
            yield Static(
                "Scan your system for installed applications and add them to tracking.",
                classes="scan-description"
            )
            with Horizontal(classes="scan-controls"):
                yield Button("Start Scan", id="start-scan-btn", variant="primary")
                yield Button("Add Selected", id="add-selected-btn", variant="success", disabled=True)
            with VerticalScroll(id="scan-results"):
                yield Static("", id="scan-status")
                yield Static("", id="scan-list")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-scan-btn":
            await self._start_scan()
        elif event.button.id == "add-selected-btn":
            await self._add_selected()
        elif event.button.id == "close-btn":
            self.app.pop_screen()

    async def _start_scan(self) -> None:
        """Start scanning for installed apps."""
        from .app import UpdateCheckerApp
        
        self.is_scanning = True
        self.selected_apps = set()
        
        status_widget = self.query_one("#scan-status", Static)
        list_widget = self.query_one("#scan-list", Static)
        add_btn = self.query_one("#add-selected-btn", Button)
        add_btn.disabled = True
        
        status_widget.update("[cyan]Scanning for installed applications...[/cyan]")
        list_widget.update("")
        
        checker_app = cast(UpdateCheckerApp, self.app)
        apps = await checker_app.scan_installed_apps()
        
        self.scanned_apps = apps
        self.is_scanning = False
        
        if not apps:
            status_widget.update("[yellow]No apps found or winget not available.[/yellow]")
            return
        
        winget_apps = [a for a in apps if a.get("source") == "winget"]
        other_apps = [a for a in apps if a.get("source") != "winget"]
        
        status_widget.update(
            f"[green]Found {len(apps)} apps:[/green] "
            f"{len(winget_apps)} from winget, {len(other_apps)} from other sources"
        )
        
        lines = ["", "[bold]Winget apps (auto-trackable):[/bold]", ""]
        for i, app in enumerate(apps):
            source = app.get("source", "unknown")
            source_style = "green" if source == "winget" else "yellow"
            marker = "○" if source == "winget" else "◌"
            lines.append(
                f"  {marker} [{source_style}]{app.get('name', 'Unknown')}[/{source_style}] "
                f"({app.get('winget_id', 'N/A')}) v{app.get('installed_version', '?')} "
                f"[dim][{source}][/dim]"
            )
        
        list_widget.update("\n".join(lines))
        add_btn.disabled = False

    async def _add_selected(self) -> None:
        """Add all winget apps to tracking."""
        status_widget = self.query_one("#scan-status", Static)
        
        existing_apps = load_apps()
        existing_ids = {app.winget_id for app in existing_apps if app.winget_id}
        
        added = 0
        skipped = 0
        
        for app_data in self.scanned_apps:
            if app_data.get("source") != "winget":
                continue
            
            winget_id = app_data.get("winget_id", "")
            if winget_id in existing_ids:
                skipped += 1
                continue
            
            new_app = App(
                name=app_data.get("name", ""),
                source=AppSource.WINGET,
                installed_version=app_data.get("installed_version"),
                winget_id=winget_id,
            )
            add_app(new_app)
            added += 1
        
        other_count = sum(1 for a in self.scanned_apps if a.get("source") != "winget")
        
        status_widget.update(
            f"[green]Added {added} apps to tracking.[/green] "
            f"Skipped {skipped} already tracked. "
            f"{other_count} non-winget apps require manual setup."
        )
        
        self.query_one("#add-selected-btn", Button).disabled = True

    def action_cancel(self) -> None:
        self.app.pop_screen()