"""Service layer for App Update Checker."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Optional

from .checkers import get_checker
from .constants import MAX_CONCURRENT_CHECKS
from .logging_config import get_logger
from .models import App, AppSource, UpdateInfo
from .utils import load_apps, save_apps

logger = get_logger(__name__)


class UpdateService:
    """Service for checking app updates.
    
    This service provides a high-level API for:
    - Checking individual apps for updates
    - Batch checking with concurrency control
    - Caching results
    - Managing app data
    """
    
    def __init__(self, max_concurrent: int = MAX_CONCURRENT_CHECKS) -> None:
        """Initialize the update service.
        
        Args:
            max_concurrent: Maximum number of concurrent update checks.
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._checker_cache: dict[AppSource, Any] = {}
    
    def _get_checker(self, source: AppSource) -> Any:
        """Get or create a checker for the source type.
        
        Uses caching to avoid creating multiple checker instances.
        
        Args:
            source: The app source type.
            
        Returns:
            The checker instance, or None if not available.
        """
        if source not in self._checker_cache:
            checker = get_checker(source)
            if checker:
                self._checker_cache[source] = checker
        return self._checker_cache.get(source)
    
    async def check_app(self, app: App) -> UpdateInfo:
        """Check a single app for updates.
        
        Args:
            app: The app to check.
            
        Returns:
            UpdateInfo with latest version and release URL.
        """
        checker = self._get_checker(app.source)
        
        if not checker:
            return UpdateInfo(
                latest_version=None,
                error=f"No checker available for source: {app.source.value}",
            )
        
        async with self._semaphore:
            try:
                logger.debug("Checking %s via %s", app.name, app.source.value)
                return await checker.check(app)
            except Exception as e:
                logger.error("Error checking %s: %s", app.name, e)
                return UpdateInfo(
                    latest_version=None,
                    error=str(e),
                )
    
    async def check_all_apps(
        self,
        apps: Optional[list[App]] = None,
        progress_callback: Optional[Callable[[App, UpdateInfo, int, int], None]] = None,
    ) -> list[tuple[App, UpdateInfo]]:
        """Check all apps for updates concurrently.
        
        Args:
            apps: List of apps to check. If None, loads from storage.
            progress_callback: Optional callback(app, info, index, total).
            
        Returns:
            List of (app, UpdateInfo) tuples.
        """
        if apps is None:
            apps = load_apps()
        
        total = len(apps)
        
        async def check_with_progress(index: int, app: App) -> tuple[App, UpdateInfo]:
            info = await self.check_app(app)
            
            if progress_callback:
                progress_callback(app, info, index + 1, total)
            
            return (app, info)
        
        tasks = [
            check_with_progress(i, app)
            for i, app in enumerate(apps)
            if not app.ignored
        ]
        
        if tasks:
            return await asyncio.gather(*tasks)
        
        return []
    
    async def check_and_update(self, apps: Optional[list[App]] = None) -> list[App]:
        """Check all apps and update their stored data.
        
        Args:
            apps: List of apps to check. If None, loads from storage.
            
        Returns:
            Updated list of apps.
        """
        if apps is None:
            apps = load_apps()
        
        results = await self.check_all_apps(apps)
        
        for app, info in results:
            for i, stored_app in enumerate(apps):
                if stored_app.id == app.id:
                    apps[i].latest_version = info.latest_version
                    apps[i].release_url = info.release_url
                    apps[i].last_error = info.error
                    apps[i].last_checked = datetime.now().isoformat()
                    break
        
        save_apps(apps)
        return apps
    
    async def scan_installed_apps(self) -> list[dict[str, str]]:
        """Scan system for installed apps using winget.
        
        Returns:
            List of dicts with app info.
        """
        checker = self._get_checker(AppSource.WINGET)
        
        if not checker:
            logger.warning("Winget checker not available")
            return []
        
        try:
            return await checker.scan_installed_apps()
        except Exception as e:
            logger.error("Error scanning installed apps: %s", e)
            return []
    
    async def detect_version_patterns(self, url: str) -> list[dict[str, Any]]:
        """Detect version patterns from a URL.
        
        Args:
            url: URL to analyze.
            
        Returns:
            List of detected patterns.
        """
        checker = self._get_checker(AppSource.CUSTOM)
        
        if not checker:
            return []
        
        try:
            return await checker.detect_version_patterns(url)
        except Exception as e:
            logger.error("Error detecting patterns: %s", e)
            return []
    
    async def validate_github_repo(self, repo: str) -> tuple[bool, Optional[str]]:
        """Validate a GitHub repository.
        
        Args:
            repo: Repository in format "owner/repo".
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        checker = self._get_checker(AppSource.GITHUB)
        
        if not checker:
            return False, "GitHub checker not available"
        
        return await checker.validate_repo(repo)
    
    async def search_winget(self, query: str) -> list[dict[str, str]]:
        """Search winget for packages.
        
        Args:
            query: Search query.
            
        Returns:
            List of matching packages.
        """
        checker = self._get_checker(AppSource.WINGET)
        
        if not checker:
            return []
        
        try:
            return await checker.search_winget(query)
        except Exception as e:
            logger.error("Error searching winget: %s", e)
            return []


_service: Optional[UpdateService] = None


def get_service() -> UpdateService:
    """Get the global update service instance.
    
    Returns:
        The global UpdateService instance.
    """
    global _service
    if _service is None:
        _service = UpdateService()
    return _service