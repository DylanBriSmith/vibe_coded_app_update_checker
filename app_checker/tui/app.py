"""Main TUI Application for App Update Checker."""

import asyncio
from datetime import datetime
from typing import Optional

from textual.app import App
from textual.containers import Container
from textual.css.query import NoMatches

from ..models import App as TrackedApp, AppSource, UpdateInfo
from ..checkers import WingetChecker, GitHubChecker, CustomChecker
from ..utils import load_apps, save_apps
from .screens import MainScreen, AddAppScreen, DetailScreen


class UpdateCheckerApp(App):
    """Main TUI application for checking app updates."""

    CSS = """
    /* Main layout */
    .main-container {
        layout: horizontal;
        height: 1fr;
    }

    /* App table */
    #app-table {
        width: 2fr;
        height: 1fr;
    }

    /* Right panel */
    .right-panel {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
        border-left: solid $primary;
    }

    .detail-panel {
        height: 1fr;
        overflow: auto;
    }

    .detail-content {
        padding: 1;
    }

    .detail-empty {
        text-align: center;
        padding: 2;
        color: $text-muted;
    }

    /* Status bar */
    #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 2;
        background: $surface;
        color: $text;
    }

    /* Add App Screen */
    .add-app-container {
        width: 70;
        height: auto;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }

    .screen-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .source-options {
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    .source-options.hidden {
        display: none;
    }

    Input {
        margin-bottom: 1;
    }

    RadioSet {
        margin-bottom: 1;
    }

    .button-row {
        layout: horizontal;
        justify-content: right;
        margin-top: 1;
        height: auto;
    }

    Button {
        margin-left: 1;
    }

    #detected-patterns {
        height: 8;
        margin-top: 1;
        padding: 1;
        background: $surface-darken-2;
    }

    #detection-result {
        height: auto;
    }

    /* Detail Screen */
    .detail-container {
        width: 60;
        height: auto;
        padding: 1 2;
        border: solid $primary;
        background: $surface;
    }

    .detail-content {
        padding: 1;
        height: auto;
    }

    /* Status colors */
    .status-ok {
        color: $success;
    }

    .status-update {
        color: $warning;
        text-style: bold;
    }

    .status-error {
        color: $error;
    }

    .status-ignored {
        color: $text-muted;
    }
    """

    SCREENS = {
        "main": MainScreen,
        "add-app": AddAppScreen,
    }

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.winget_checker = WingetChecker()
        self.github_checker = GitHubChecker()
        self.custom_checker = CustomChecker()

    def on_mount(self) -> None:
        self.push_screen("main")

    async def check_app(self, app: TrackedApp) -> UpdateInfo:
        """Check a single app for updates.

        Args:
            app: The app to check.

        Returns:
            UpdateInfo with the latest version.
        """
        if app.source == AppSource.WINGET:
            return await self.winget_checker.check(app)
        elif app.source == AppSource.GITHUB:
            return await self.github_checker.check(app)
        elif app.source == AppSource.CUSTOM:
            return await self.custom_checker.check(app)
        else:
            return UpdateInfo(
                latest_version=None,
                error=f"Unknown source type: {app.source}",
            )

    async def scan_installed_apps(self) -> list[dict]:
        """Scan system for installed apps using winget.

        Returns:
            List of dicts with app info.
        """
        return await self.winget_checker.scan_installed_apps()

    async def detect_version_patterns(self, url: str) -> list[dict]:
        """Detect version patterns from a URL.

        Args:
            url: URL to analyze.

        Returns:
            List of detected patterns.
        """
        return await self.custom_checker.detect_version_patterns(url)

    async def validate_github_repo(self, repo: str) -> tuple[bool, Optional[str]]:
        """Validate a GitHub repository.

        Args:
            repo: Repository in format "owner/repo".

        Returns:
            Tuple of (is_valid, error_message).
        """
        return await self.github_checker.validate_repo(repo)

    async def search_winget(self, query: str) -> list[dict]:
        """Search winget for packages.

        Args:
            query: Search query.

        Returns:
            List of matching packages.
        """
        if not query:
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                "winget", "search", query, "--source", "winget",
                "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="ignore")

            results = []
            lines = output.split("\n")

            for line in lines:
                line = line.strip()
                if not line or line.startswith("Name") or line.startswith("-"):
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    name = " ".join(parts[:-1])
                    pkg_id = parts[-1]
                    results.append({"name": name, "id": pkg_id})

            return results[:10]
        except Exception:
            return []


def run_tui():
    """Run the TUI application."""
    app = UpdateCheckerApp()
    app.run()