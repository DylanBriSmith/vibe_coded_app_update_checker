"""Winget checker - uses Windows Package Manager."""

import asyncio
import json
import re
import shutil
from typing import Any, Optional

from ..constants import WINGET_TIMEOUT, WINGET_SEARCH_TIMEOUT
from ..logging_config import get_logger
from ..models import App, AppSource, UpdateInfo
from .base import BaseChecker

logger = get_logger(__name__)


class WingetChecker(BaseChecker):
    """Check for updates using Windows Package Manager (winget)."""

    @property
    def source_type(self) -> str:
        return "winget"

    def can_check(self, app: App) -> bool:
        return app.source == AppSource.WINGET and app.winget_id is not None

    async def check(self, app: App) -> UpdateInfo:
        """Check for updates using winget.
        
        Args:
            app: The app to check for updates.
            
        Returns:
            UpdateInfo with latest version from winget.
        """
        if not app.winget_id:
            return UpdateInfo(
                latest_version=None,
                error="No winget_id configured for this app"
            )

        if not self._is_winget_available():
            return UpdateInfo(
                latest_version=None,
                error="Winget is not available on this system",
                installed_version=app.installed_version
            )

        try:
            result = await self._run_winget_show(app.winget_id)
            if result:
                return UpdateInfo(
                    latest_version=result.get("version"),
                    release_url=result.get("homepage"),
                    installed_version=app.installed_version
                )
            return UpdateInfo(
                latest_version=None,
                error="Could not fetch winget info",
                installed_version=app.installed_version
            )
        except asyncio.TimeoutError:
            logger.error("Timeout checking %s via winget", app.winget_id)
            return UpdateInfo(
                latest_version=None,
                error="Timeout while checking winget",
                installed_version=app.installed_version
            )
        except Exception as e:
            logger.exception("Error checking %s via winget", app.winget_id)
            return UpdateInfo(
                latest_version=None,
                error=str(e),
                installed_version=app.installed_version
            )

    async def _run_winget_show(self, winget_id: str) -> Optional[dict[str, Optional[str]]]:
        """Run winget show to get package info.
        
        Args:
            winget_id: The winget package ID.
            
        Returns:
            Dict with version and homepage, or None if failed.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "winget", "show", "--id", winget_id, "--source", "winget",
                "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=WINGET_SEARCH_TIMEOUT
            )
            
            if proc.returncode != 0:
                logger.debug("Winget show returned %d for %s", proc.returncode, winget_id)
                return None
            
            output = stdout.decode("utf-8", errors="ignore")
            return self._parse_winget_show_output(output)
            
        except asyncio.TimeoutError:
            logger.warning("Winget show timed out for %s", winget_id)
            raise
        except Exception as e:
            logger.error("Winget show error for %s: %s", winget_id, e)
            return None

    def _parse_winget_show_output(self, output: str) -> Optional[dict[str, Optional[str]]]:
        """Parse winget show output to extract version and homepage.
        
        Args:
            output: Raw winget show output.
            
        Returns:
            Dict with version and homepage.
        """
        version: Optional[str] = None
        homepage: Optional[str] = None
        
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
            elif line.startswith("Homepage:"):
                homepage = line.split(":", 1)[1].strip()
                
        if version:
            return {"version": version, "homepage": homepage}
        return None

    def _is_winget_available(self) -> bool:
        """Check if winget is available on the system."""
        return shutil.which("winget") is not None

    async def scan_installed_apps(self) -> list[dict[str, str]]:
        """Scan system for installed apps using winget.
        
        Returns:
            List of dicts with app info (name, id, version).
        """
        if not self._is_winget_available():
            logger.warning("Winget not available for scanning")
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                "winget", "list", "--format", "json",
                "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=WINGET_TIMEOUT
            )
            
            if proc.returncode != 0:
                logger.warning("Winget list returned %d", proc.returncode)
                return []
            
            output = stdout.decode("utf-8", errors="ignore")
            apps = self._parse_winget_list_output(output)
            logger.info("Scanned %d installed apps", len(apps))
            return apps
            
        except asyncio.TimeoutError:
            logger.error("Winget list timed out")
            return []
        except Exception as e:
            logger.exception("Error scanning installed apps: %s", e)
            return []

    def _parse_winget_list_output(self, output: str) -> list[dict[str, str]]:
        """Parse winget list JSON output.
        
        Args:
            output: Raw JSON output from winget list.
            
        Returns:
            List of dicts with app info including actual source.
        """
        try:
            data = json.loads(output)
            apps: list[dict[str, str]] = []
            
            for source_data in data.get("Sources", []):
                source_name = source_data.get("Source", "unknown")
                for pkg in source_data.get("Packages", []):
                    apps.append({
                        "name": pkg.get("Name", ""),
                        "winget_id": pkg.get("Id", ""),
                        "installed_version": pkg.get("Version", ""),
                        "source": source_name,
                    })
                    
            return apps
        except json.JSONDecodeError as e:
            logger.error("Failed to parse winget list output: %s", e)
            return []

    async def search_winget(self, query: str) -> list[dict[str, str]]:
        """Search winget for packages.
        
        Args:
            query: Search query.
            
        Returns:
            List of matching packages with name and id.
        """
        if not self._is_winget_available():
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                "winget", "search", query, "--source", "winget",
                "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=WINGET_SEARCH_TIMEOUT
            )
            
            if proc.returncode != 0:
                return []
            
            output = stdout.decode("utf-8", errors="ignore")
            return self._parse_winget_search_output(output)
            
        except asyncio.TimeoutError:
            logger.warning("Winget search timed out for: %s", query)
            return []
        except Exception as e:
            logger.error("Winget search error: %s", e)
            return []

    def _parse_winget_search_output(self, output: str) -> list[dict[str, str]]:
        """Parse winget search output.
        
        Args:
            output: Raw winget search output.
            
        Returns:
            List of dicts with name and id.
        """
        results: list[dict[str, str]] = []
        lines = output.split("\n")
        
        header_found = False
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            if line.startswith("Name") and "Id" in line:
                header_found = True
                continue
            
            if line.startswith("-"):
                continue
            
            if not header_found:
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                name_parts = []
                id_part = ""
                
                for i, part in enumerate(parts):
                    if re.match(r'^[A-Za-z0-9]+\.[A-Za-z0-9.]+$', part):
                        id_part = part
                        name_parts = parts[:i]
                        break
                
                if id_part and name_parts:
                    results.append({
                        "name": " ".join(name_parts),
                        "id": id_part
                    })
        
        return results[:10]

    async def check_for_updates(self) -> list[dict[str, str]]:
        """Check all installed apps for available updates.
        
        Returns:
            List of dicts with apps that have updates available.
        """
        if not self._is_winget_available():
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                "winget", "upgrade", "--include-unknown",
                "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=WINGET_TIMEOUT
            )
            
            if proc.returncode != 0:
                return []
            
            output = stdout.decode("utf-8", errors="ignore")
            return self._parse_winget_upgrade_output(output)
            
        except asyncio.TimeoutError:
            logger.error("Winget upgrade check timed out")
            return []
        except Exception as e:
            logger.exception("Error checking for updates: %s", e)
            return []

    def _parse_winget_upgrade_output(self, output: str) -> list[dict[str, str]]:
        """Parse winget upgrade output to find apps with updates.
        
        Args:
            output: Raw winget upgrade output.
            
        Returns:
            List of dicts with update info.
        """
        updates: list[dict[str, str]] = []
        lines = output.split("\n")
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Name") or line.startswith("-"):
                continue
                
            parts = line.split()
            if len(parts) >= 3:
                name = parts[0]
                installed = parts[-2] if len(parts) >= 2 else ""
                available = parts[-1] if len(parts) >= 1 else ""
                
                if installed and available and installed != available:
                    updates.append({
                        "name": name,
                        "installed_version": installed,
                        "latest_version": available,
                    })
                    
        return updates