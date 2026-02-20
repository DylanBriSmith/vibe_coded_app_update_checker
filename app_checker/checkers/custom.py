"""Custom URL checker with regex version extraction."""

import re
from typing import Optional

import httpx

from ..models import App, AppSource, UpdateInfo
from .base import BaseChecker


class CustomChecker(BaseChecker):
    """Check for updates using custom URL and regex pattern."""

    DEFAULT_VERSION_PATTERNS = [
        r"[Vv]ersion[:\s]+(\d+(?:\.\d+)*)",
        r"[Vv](\d+(?:\.\d+)+)",
        r"[Ll]atest[:\s]+(\d+(?:\.\d+)*)",
        r"(\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+)?)",
        r"(\d+\.\d+)",
    ]

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
            return UpdateInfo(
                latest_version=None,
                error=f"HTTP error: {e.response.status_code}",
                installed_version=app.installed_version
            )
        except Exception as e:
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

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
            if match:
                return match.group(1)
        except re.error:
            pass
        return None

    def _auto_detect_version(self, content: str) -> Optional[str]:
        """Auto-detect version using common patterns.
        
        Args:
            content: Page content.
            
        Returns:
            First detected version string, or None if not found.
        """
        for pattern in self.DEFAULT_VERSION_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
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

            patterns_found = []
            
            for pattern in self.DEFAULT_VERSION_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    unique_matches = list(set(matches))[:5]
                    patterns_found.append({
                        "pattern": pattern,
                        "examples": unique_matches,
                        "count": len(matches),
                    })

            patterns_found.sort(key=lambda x: x["count"], reverse=True)
            return patterns_found[:10]
            
        except Exception:
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