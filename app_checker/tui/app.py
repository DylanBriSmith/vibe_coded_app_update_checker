"""Main TUI Application for App Update Checker."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.app import App as TextualApp

from ..models import App as AppModel, UpdateInfo
from ..service import UpdateService, get_service
from .screens import AddAppScreen, DetailScreen, MainScreen, ScanScreen

if TYPE_CHECKING:
    pass

CSS_PATH = Path(__file__).parent / "styles.tcss"

SCREENS = {
    "main": MainScreen,
    "add-app": AddAppScreen,
    "detail": DetailScreen,
    "scan": ScanScreen,
}


class UpdateCheckerApp(TextualApp):
    """Main TUI application for checking app updates."""

    CSS_PATH = CSS_PATH
    SCREENS = SCREENS

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._service: UpdateService | None = None

    @property
    def service(self) -> UpdateService:
        """Get the update service instance."""
        if self._service is None:
            self._service = get_service()
        return self._service

    def on_mount(self) -> None:
        self.push_screen("main")

    async def check_app(self, app: AppModel) -> UpdateInfo:
        """Check a single app for updates.

        Args:
            app: The app to check.

        Returns:
            UpdateInfo with the latest version.
        """
        return await self.service.check_app(app)

    async def scan_installed_apps(self) -> list[dict[str, str]]:
        """Scan system for installed apps using winget.

        Returns:
            List of dicts with app info.
        """
        return await self.service.scan_installed_apps()

    async def detect_version_patterns(self, url: str) -> list[dict[str, Any]]:
        """Detect version patterns from a URL.

        Args:
            url: URL to analyze.

        Returns:
            List of detected patterns.
        """
        return await self.service.detect_version_patterns(url)

    async def validate_github_repo(self, repo: str) -> tuple[bool, str | None]:
        """Validate a GitHub repository.

        Args:
            repo: Repository in format "owner/repo".

        Returns:
            Tuple of (is_valid, error_message).
        """
        return await self.service.validate_github_repo(repo)

    async def search_winget(self, query: str) -> list[dict[str, str]]:
        """Search winget for packages.

        Args:
            query: Search query.

        Returns:
            List of matching packages.
        """
        return await self.service.search_winget(query)


def run_tui() -> None:
    """Run the TUI application."""
    app = UpdateCheckerApp()
    app.run()