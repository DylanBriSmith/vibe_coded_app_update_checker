"""Homebrew checker for macOS."""

import asyncio
import json
import shutil
from typing import Optional

from ..constants import HOMEBREW_TIMEOUT
from ..logging_config import get_logger
from ..models import App, AppSource, UpdateInfo
from .base import BaseChecker

logger = get_logger(__name__)


class HomebrewChecker(BaseChecker):
    """Check for updates using Homebrew (macOS)."""

    @property
    def source_type(self) -> str:
        return "homebrew"

    def can_check(self, app: App) -> bool:
        return app.source == AppSource.HOMEBREW and app.homebrew_formula is not None

    async def check(self, app: App) -> UpdateInfo:
        """Check for updates using Homebrew.
        
        Args:
            app: The app to check for updates.
            
        Returns:
            UpdateInfo with latest version from Homebrew.
        """
        if not app.homebrew_formula:
            return UpdateInfo(
                latest_version=None,
                error="No homebrew_formula configured for this app",
                installed_version=app.installed_version
            )

        if not self._is_homebrew_available():
            return UpdateInfo(
                latest_version=None,
                error="Homebrew is not available on this system",
                installed_version=app.installed_version
            )

        try:
            info = await self._get_formula_info(app.homebrew_formula)
            if info:
                return UpdateInfo(
                    latest_version=info.get("version"),
                    release_url=info.get("homepage"),
                    installed_version=app.installed_version
                )
            return UpdateInfo(
                latest_version=None,
                error="Formula not found",
                installed_version=app.installed_version
            )
        except asyncio.TimeoutError:
            logger.error("Timeout checking %s via Homebrew", app.homebrew_formula)
            return UpdateInfo(
                latest_version=None,
                error="Timeout while checking Homebrew",
                installed_version=app.installed_version
            )
        except Exception as e:
            logger.exception("Error checking %s via Homebrew", app.homebrew_formula)
            return UpdateInfo(
                latest_version=None,
                error=str(e),
                installed_version=app.installed_version
            )

    def _is_homebrew_available(self) -> bool:
        """Check if Homebrew is available on the system."""
        return shutil.which("brew") is not None

    async def _get_formula_info(self, formula: str) -> Optional[dict]:
        """Get formula info from Homebrew.
        
        Args:
            formula: The Homebrew formula name.
            
        Returns:
            Dict with version and homepage, or None if not found.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "brew", "info", formula, "--json=v2",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=HOMEBREW_TIMEOUT
            )

            if proc.returncode != 0:
                logger.debug("brew info returned %d for %s", proc.returncode, formula)
                return None

            data = json.loads(stdout.decode("utf-8"))
            
            for formula_data in data.get("formulae", []):
                if formula_data.get("name") == formula or formula_data.get("full_name") == formula:
                    return {
                        "version": formula_data.get("version"),
                        "homepage": formula_data.get("homepage"),
                    }
            
            for cask_data in data.get("casks", []):
                if cask_data.get("token") == formula or cask_data.get("full_name") == formula:
                    return {
                        "version": cask_data.get("version"),
                        "homepage": cask_data.get("homepage"),
                    }
            
            return None

        except json.JSONDecodeError as e:
            logger.error("Failed to parse brew info output: %s", e)
            return None
        except asyncio.TimeoutError:
            logger.warning("brew info timed out for %s", formula)
            raise
        except Exception as e:
            logger.error("Error getting formula info: %s", e)
            return None

    async def scan_installed_apps(self) -> list[dict[str, str]]:
        """Scan system for installed apps using Homebrew.
        
        Returns:
            List of dicts with app info.
        """
        if not self._is_homebrew_available():
            logger.warning("Homebrew not available for scanning")
            return []

        apps = []
        
        apps.extend(await self._scan_formulae())
        apps.extend(await self._scan_casks())
        
        logger.info("Scanned %d installed Homebrew packages", len(apps))
        return apps

    async def _scan_formulae(self) -> list[dict[str, str]]:
        """Scan installed Homebrew formulae."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "brew", "list", "--formula", "--json=v2",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=HOMEBREW_TIMEOUT
            )

            if proc.returncode != 0:
                return []

            data = json.loads(stdout.decode("utf-8"))
            apps = []
            
            for formula in data.get("formulae", []):
                apps.append({
                    "name": formula.get("name", ""),
                    "homebrew_formula": formula.get("full_name", formula.get("name", "")),
                    "installed_version": formula.get("installed_version", ""),
                    "source": "homebrew",
                    "type": "formula",
                })
            
            return apps

        except Exception as e:
            logger.error("Error scanning Homebrew formulae: %s", e)
            return []

    async def _scan_casks(self) -> list[dict[str, str]]:
        """Scan installed Homebrew casks."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "brew", "list", "--cask",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=HOMEBREW_TIMEOUT
            )

            if proc.returncode != 0:
                return []

            output = stdout.decode("utf-8").strip()
            if not output:
                return []

            casks = []
            for line in output.split("\n"):
                if line.strip():
                    casks.append({
                        "name": line.strip(),
                        "homebrew_formula": line.strip(),
                        "installed_version": "",
                        "source": "homebrew",
                        "type": "cask",
                    })
            
            return casks

        except Exception as e:
            logger.error("Error scanning Homebrew casks: %s", e)
            return []

    async def search_formula(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        """Search Homebrew for a formula.
        
        Args:
            query: Search query.
            limit: Maximum results to return.
            
        Returns:
            List of matching formulae.
        """
        if not self._is_homebrew_available():
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                "brew", "search", "--formula", query,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=HOMEBREW_TIMEOUT
            )

            if proc.returncode != 0:
                return []

            output = stdout.decode("utf-8").strip()
            if not output:
                return []

            results = []
            for line in output.split("\n")[:limit]:
                formula = line.strip()
                if formula and not formula.startswith("==>"):
                    results.append({
                        "name": formula,
                        "homebrew_formula": formula,
                    })
            
            return results

        except Exception as e:
            logger.error("Error searching Homebrew: %s", e)
            return []