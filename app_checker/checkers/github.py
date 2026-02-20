"""GitHub releases checker."""

import re
from typing import Optional

import httpx

from ..models import App, AppSource, UpdateInfo
from .base import BaseChecker


class GitHubChecker(BaseChecker):
    """Check for updates using GitHub releases API."""

    GITHUB_API_BASE = "https://api.github.com"

    @property
    def source_type(self) -> str:
        return "github"

    def can_check(self, app: App) -> bool:
        return app.source == AppSource.GITHUB and app.github_repo is not None

    async def check(self, app: App) -> UpdateInfo:
        """Check for updates using GitHub releases API.
        
        Args:
            app: The app to check for updates.
            
        Returns:
            UpdateInfo with latest version from GitHub releases.
        """
        if not app.github_repo:
            return UpdateInfo(
                latest_version=None,
                error="No github_repo configured for this app"
            )

        try:
            release = await self._get_latest_release(app.github_repo)
            if release:
                version = self._extract_version(release.get("tag_name", ""))
                return UpdateInfo(
                    latest_version=version,
                    release_url=release.get("html_url"),
                    installed_version=app.installed_version
                )
            return UpdateInfo(
                latest_version=None,
                error="No releases found for this repository",
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

    async def _get_latest_release(self, repo: str) -> Optional[dict]:
        """Get the latest release for a GitHub repository.
        
        Args:
            repo: Repository in format "owner/repo".
            
        Returns:
            Dict with release info, or None if not found.
        """
        url = f"{self.GITHUB_API_BASE}/repos/{repo}/releases/latest"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    def _extract_version(self, tag: str) -> str:
        """Extract version number from a tag.
        
        Args:
            tag: Tag name (e.g., "v1.2.3" or "1.2.3").
            
        Returns:
            Version string without 'v' prefix.
        """
        if tag.startswith("v"):
            return tag[1:]
        return tag

    async def validate_repo(self, repo: str) -> tuple[bool, Optional[str]]:
        """Validate that a GitHub repository exists.
        
        Args:
            repo: Repository in format "owner/repo".
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        if not re.match(r"^[\w-]+/[\w.-]+$", repo):
            return False, "Invalid repository format. Use 'owner/repo'"
        
        url = f"{self.GITHUB_API_BASE}/repos/{repo}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return True, None
                elif response.status_code == 404:
                    return False, "Repository not found"
                else:
                    return False, f"HTTP error: {response.status_code}"
        except Exception as e:
            return False, str(e)

    async def search_repo(self, query: str, limit: int = 10) -> list[dict]:
        """Search for GitHub repositories.
        
        Args:
            query: Search query.
            limit: Maximum number of results.
            
        Returns:
            List of dicts with repo info.
        """
        url = f"{self.GITHUB_API_BASE}/search/repositories"
        params = {"q": query, "per_page": limit}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                return [
                    {
                        "full_name": item["full_name"],
                        "name": item["name"],
                        "description": item.get("description", ""),
                        "stars": item.get("stargazers_count", 0),
                    }
                    for item in data.get("items", [])
                ]
        except Exception:
            return []