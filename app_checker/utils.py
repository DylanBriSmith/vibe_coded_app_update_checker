"""Utility functions for App Update Checker."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from .constants import APPS_FILE, BACKUP_FILE, DEFAULT_DATA_DIR
from .logging_config import get_logger
from .models import App, AppSource

logger = get_logger(__name__)

_data_dir: Optional[Path] = None


def set_data_dir(path: Path) -> None:
    """Set a custom data directory path.
    
    Args:
        path: The data directory path to use.
    """
    global _data_dir
    _data_dir = path


def get_data_dir() -> Path:
    """Get the data directory path."""
    return _data_dir if _data_dir is not None else DEFAULT_DATA_DIR


def get_apps_file() -> Path:
    """Get the apps.json file path."""
    return get_data_dir() / APPS_FILE


def get_backup_file() -> Path:
    """Get the backup file path."""
    return get_data_dir() / BACKUP_FILE


def ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)


def _create_backup() -> bool:
    """Create a backup of the current apps file.
    
    Returns:
        True if backup was created, False otherwise.
    """
    apps_file = get_apps_file()
    backup_file = get_backup_file()
    
    if not apps_file.exists():
        return False
    
    try:
        ensure_data_dir()
        shutil.copy2(apps_file, backup_file)
        logger.debug("Created backup at %s", backup_file)
        return True
    except OSError as e:
        logger.error("Failed to create backup: %s", e)
        return False


def _restore_backup() -> bool:
    """Restore apps from backup file.
    
    Returns:
        True if restore was successful, False otherwise.
    """
    backup_file = get_backup_file()
    apps_file = get_apps_file()
    
    if not backup_file.exists():
        logger.warning("No backup file found at %s", backup_file)
        return False
    
    try:
        shutil.copy2(backup_file, apps_file)
        logger.info("Restored from backup at %s", backup_file)
        return True
    except OSError as e:
        logger.error("Failed to restore from backup: %s", e)
        return False


def load_apps() -> list[App]:
    """Load apps from the JSON file.
    
    Returns:
        List of App objects. Returns empty list if file doesn't exist.
        
    Raises:
        RuntimeError: If file is corrupted and no backup is available.
    """
    apps_file = get_apps_file()
    
    if not apps_file.exists():
        logger.debug("Apps file does not exist, returning empty list")
        return []
    
    try:
        with open(apps_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        apps = [App.from_dict(app_data) for app_data in data.get("apps", [])]
        logger.debug("Loaded %d apps from %s", len(apps), apps_file)
        return apps
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse apps file: %s", e)
        
        if _restore_backup():
            return load_apps()
        
        raise RuntimeError(
            f"Apps file is corrupted and no backup available. "
            f"Manual intervention required at: {apps_file}"
        ) from e
        
    except KeyError as e:
        logger.error("Invalid apps file format: missing key %s", e)
        
        if _restore_backup():
            return load_apps()
        
        raise RuntimeError(
            f"Apps file has invalid format. "
            f"Manual intervention required at: {apps_file}"
        ) from e


def save_apps(apps: list[App]) -> None:
    """Save apps to the JSON file with backup.
    
    Args:
        apps: List of App objects to save.
        
    Raises:
        OSError: If file cannot be written.
    """
    ensure_data_dir()
    apps_file = get_apps_file()
    
    _create_backup()
    
    data = {
        "apps": [app.to_dict() for app in apps],
        "last_updated": datetime.now().isoformat(),
    }
    
    temp_file = apps_file.with_suffix(".tmp")
    
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        temp_file.replace(apps_file)
        logger.debug("Saved %d apps to %s", len(apps), apps_file)
        
    except OSError as e:
        logger.error("Failed to save apps: %s", e)
        if temp_file.exists():
            temp_file.unlink()
        raise


def add_app(app: App) -> None:
    """Add a new app to the list.
    
    Args:
        app: App object to add.
    """
    apps = load_apps()
    
    for existing in apps:
        if existing.id == app.id:
            logger.warning("App with id %s already exists, skipping", app.id)
            return
    
    apps.append(app)
    save_apps(apps)
    logger.info("Added app: %s", app.name)


def update_app(app: App) -> bool:
    """Update an existing app in the list.
    
    Args:
        app: App object with updated data.
        
    Returns:
        True if app was found and updated, False otherwise.
    """
    apps = load_apps()
    
    for i, existing_app in enumerate(apps):
        if existing_app.id == app.id:
            apps[i] = app
            save_apps(apps)
            logger.debug("Updated app: %s", app.name)
            return True
    
    logger.warning("App with id %s not found for update", app.id)
    return False


def delete_app(app_id: str) -> bool:
    """Delete an app from the list.
    
    Args:
        app_id: ID of the app to delete.
        
    Returns:
        True if app was deleted, False if not found.
    """
    apps = load_apps()
    original_count = len(apps)
    apps = [app for app in apps if app.id != app_id]
    
    if len(apps) < original_count:
        save_apps(apps)
        logger.info("Deleted app with id: %s", app_id)
        return True
    
    logger.warning("App with id %s not found for deletion", app_id)
    return False


def get_app_by_id(app_id: str) -> Optional[App]:
    """Get an app by its ID.
    
    Args:
        app_id: ID of the app to find.
        
    Returns:
        App object if found, None otherwise.
    """
    apps = load_apps()
    
    for app in apps:
        if app.id == app_id:
            return app
    
    return None


def get_app_by_name(name: str) -> Optional[App]:
    """Get an app by its name (case-insensitive).
    
    Args:
        name: Name of the app to find.
        
    Returns:
        App object if found, None otherwise.
    """
    apps = load_apps()
    name_lower = name.lower()
    
    for app in apps:
        if app.name.lower() == name_lower:
            return app
    
    return None


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers.
    
    Handles pre-release tags by stripping them.
    E.g., "1.0.0-beta" -> (1, 0, 0)
    
    Args:
        version: Version string (e.g., "1.2.3").
        
    Returns:
        Tuple of integers (e.g., (1, 2, 3)).
    """
    if not version:
        return (0,)
    
    version = version.strip()
    
    if version.lower().startswith("v"):
        version = version[1:]
    
    dash_idx = version.find("-")
    if dash_idx > 0:
        version = version[:dash_idx]
    
    plus_idx = version.find("+")
    if plus_idx > 0:
        version = version[:plus_idx]
    
    parts = []
    
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            break
    
    return tuple(parts) if parts else (0,)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings.
    
    Args:
        v1: First version string.
        v2: Second version string.
        
    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2.
    """
    p1 = parse_version(v1)
    p2 = parse_version(v2)
    
    if p1 < p2:
        return -1
    elif p1 > p2:
        return 1
    return 0


def normalize_version(version: Optional[str]) -> Optional[str]:
    """Normalize a version string.
    
    Args:
        version: Version string to normalize.
        
    Returns:
        Normalized version string without 'v' prefix.
    """
    if not version:
        return None
    
    version = version.strip()
    
    if version.lower().startswith("v"):
        version = version[1:]
    
    return version if version else None


def is_update_available(app: App) -> bool:
    """Check if an update is available for an app.
    
    Args:
        app: App to check.
        
    Returns:
        True if update is available, False otherwise.
    """
    if app.ignored:
        return False
    
    if not app.installed_version or not app.latest_version:
        return False
    
    return compare_versions(app.installed_version, app.latest_version) < 0