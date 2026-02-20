"""Custom URL checker with regex version extraction."""

import re
from typing import Optional

import httpx

from ..constants import (
    CUSTOM_URL_TIMEOUT,
    DEFAULT_USER_AGENT,
    DEFAULT_VERSION_PATTERNS,
    MAX_DETECTED_PATTERNS,
    MAX_UNIQUE_MATCHES,
)
from ..logging_config import get_logger
from ..models import App, AppSource, UpdateInfo
from .base import BaseChecker

logger = get_logger(__name__)


class CustomChecker(BaseChecker):
    """Check for updates using custom URL and regex pattern."""

    @property
    def source_type(self) -> str:
        return "custom"

    def can_check(self, app: App) -> bool:
        return app.source == AppSource.CUSTOM and app.custom_url is not None

    async def check(self, app: App) -> UpdateInfo:
        """Check for updates using custom URL.
        
        Args:
            app: The app to check for updates.
            
        Returns:
            UpdateInfo with latest version extracted from URL.
        """
        if not app.custom_url:
            return UpdateInfo(
                latest_version=None,
                error="No custom_url configured for this app"
            )

        try:
            content = await self._fetch_url(app.custom_url)
            if not content:
                return UpdateInfo(
                    latest_version=None,
                    error="Failed to fetch URL content",
                    installed_version=app.installed_version
                )

            if app.version_regex:
                version = self._extract_with_regex(content, app.version_regex)
            else:
                version = self._auto_detect_version(content)

            if version:
                return UpdateInfo(
                    latest_version=version,
                    release_url=app.custom_url,
                    installed_version=app.installed_version
                )
            return UpdateInfo(
                latest_version=None,
                error="Could not extract version from page",
                installed_version=app.installed_version
            )
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error: {e.response.status_code}"
            logger.error("HTTP error fetching %s: %s", app.custom_url, error_msg)
            return UpdateInfo(
                latest_version=None,
                error=error_msg,
                installed_version=app.installed_version
            )
        except Exception as e:
            logger.exception("Error checking %s", app.custom_url)
            return UpdateInfo(
                latest_version=None,
                error=str(e),
                installed_version=app.installed_version
            )

    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from a URL.
        
        Args:
            url: URL to fetch.
            
        Returns:
            Page content as string, or None if failed.
        """
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        try:
            async with httpx.AsyncClient(
                timeout=CUSTOM_URL_TIMEOUT,
                follow_redirects=True,
                max_redirects=10,
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error("Error fetching %s: %s", url, e)
            return None

    def _extract_with_regex(self, content: str, pattern: str) -> Optional[str]:
        """Extract version using a specific regex pattern.
        
        Args:
            content: Page content.
            pattern: Regex pattern with capture group for version.
            
        Returns:
            Extracted version string, or None if not found.
        """
        try:
            match = re.search(pattern, content, re.IGNORECASE)
            if match and match.groups():
                return match.group(1)
        except re.error as e:
            logger.error("Invalid regex pattern '%s': %s", pattern, e)
        return None

    def _auto_detect_version(self, content: str) -> Optional[str]:
        """Auto-detect version using common patterns.
        
        Args:
            content: Page content.
            
        Returns:
            First detected version string, or None if not found.
        """
        for pattern in DEFAULT_VERSION_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match and match.groups():
                return match.group(1)
        return None

    async def detect_version_patterns(self, url: str) -> list[dict]:
        """Detect potential version patterns from a URL.
        
        Args:
            url: URL to analyze.
            
        Returns:
            List of dicts with detected patterns and example matches.
        """
        try:
            content = await self._fetch_url(url)
            if not content:
                return []

            patterns_found: list[dict] = []
            
            for pattern in DEFAULT_VERSION_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    unique_matches = list(set(matches))[:MAX_UNIQUE_MATCHES]
                    patterns_found.append({
                        "pattern": pattern,
                        "examples": unique_matches,
                        "count": len(matches),
                    })

            patterns_found.sort(key=lambda x: x["count"], reverse=True)
            return patterns_found[:MAX_DETECTED_PATTERNS]
            
        except Exception as e:
            logger.error("Error detecting patterns from %s: %s", url, e)
            return []

    async def test_custom_checker(
        self, url: str, regex: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Test a custom checker configuration.
        
        Args:
            url: URL to test.
            regex: Optional regex pattern to use.
            
        Returns:
            Tuple of (success, version, error_message).
        """
        try:
            content = await self._fetch_url(url)
            if not content:
                return False, None, "Failed to fetch URL content"

            if regex:
                version = self._extract_with_regex(content, regex)
            else:
                version = self._auto_detect_version(content)

            if version:
                return True, version, None
            return False, None, "Could not extract version from page"
            
        except Exception as e:
            return False, None, str(e)