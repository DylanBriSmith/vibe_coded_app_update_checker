"""Winget checker - uses Windows Package Manager."""

import asyncio
import json
import shutil
from typing import Optional

from ..models import App, AppSource, UpdateInfo
from .base import BaseChecker


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
                error="Could not fetch winget info"
            )
        except Exception as e:
            return UpdateInfo(
                latest_version=None,
                error=str(e),
                installed_version=app.installed_version
            )

    async def _run_winget_show(self, winget_id: str) -> Optional[dict]:
        """Run winget show to get package info.
        
        Args:
            winget_id: The winget package ID.
            
        Returns:
            Dict with version and homepage, or None if failed.
        """
        if not self._is_winget_available():
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                "winget", "show", "--id", winget_id, "--source", "winget",
                "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            
            if proc.returncode != 0:
                return None
            
            output = stdout.decode("utf-8", errors="ignore")
            return self._parse_winget_show_output(output)
            
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    def _parse_winget_show_output(self, output: str) -> Optional[dict]:
        """Parse winget show output to extract version and homepage.
        
        Args:
            output: Raw winget show output.
            
        Returns:
            Dict with version and homepage.
        """
        version = None
        homepage = None
        
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

    async def scan_installed_apps(self) -> list[dict]:
        """Scan system for installed apps using winget.
        
        Returns:
            List of dicts with app info (name, id, version).
        """
        if not self._is_winget_available():
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                "winget", "list", "--format", "json",
                "--accept-source-agreements",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            
            if proc.returncode != 0:
                return []
            
            output = stdout.decode("utf-8", errors="ignore")
            return self._parse_winget_list_output(output)
            
        except asyncio.TimeoutError:
            return []
        except Exception:
            return []

    def _parse_winget_list_output(self, output: str) -> list[dict]:
        """Parse winget list JSON output.
        
        Args:
            output: Raw JSON output from winget list.
            
        Returns:
            List of dicts with app info.
        """
        try:
            data = json.loads(output)
            apps = []
            
            for source in data.get("Sources", []):
                for pkg in source.get("Packages", []):
                    apps.append({
                        "name": pkg.get("Name", ""),
                        "winget_id": pkg.get("Id", ""),
                        "installed_version": pkg.get("Version", ""),
                        "source": "winget"
                    })
                    
            return apps
        except json.JSONDecodeError:
            return []

    async def check_for_updates(self) -> list[dict]:
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
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            
            if proc.returncode != 0:
                return []
            
            output = stdout.decode("utf-8", errors="ignore")
            return self._parse_winget_upgrade_output(output)
            
        except asyncio.TimeoutError:
            return []
        except Exception:
            return []

    def _parse_winget_upgrade_output(self, output: str) -> list[dict]:
        """Parse winget upgrade output to find apps with updates.
        
        Args:
            output: Raw winget upgrade output.
            
        Returns:
            List of dicts with update info.
        """
        updates = []
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