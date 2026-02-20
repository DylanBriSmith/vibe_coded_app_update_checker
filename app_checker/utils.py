"""Utility functions for App Update Checker."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import App, AppSource

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
APPS_FILE = "apps.json"


def get_data_dir() -> Path:
    """Get the data directory path."""
    return DEFAULT_DATA_DIR


def get_apps_file() -> Path:
    """Get the apps.json file path."""
    return get_data_dir() / APPS_FILE


def ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)


def load_apps() -> list[App]:
    """Load apps from the JSON file.
    
    Returns:
        List of App objects.
    """
    apps_file = get_apps_file()
    
    if not apps_file.exists():
        return []
    
    try:
        with open(apps_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return [App.from_dict(app_data) for app_data in data.get("apps", [])]
    except (json.JSONDecodeError, KeyError):
        return []


def save_apps(apps: list[App]) -> None:
    """Save apps to the JSON file.
    
    Args:
        apps: List of App objects to save.
    """
    ensure_data_dir()
    apps_file = get_apps_file()
    
    data = {
        "apps": [app.to_dict() for app in apps],
        "last_updated": datetime.now().isoformat(),
    }
    
    with open(apps_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_app(app: App) -> None:
    """Add a new app to the list.
    
    Args:
        app: App object to add.
    """
    apps = load_apps()
    apps.append(app)
    save_apps(apps)


def update_app(app: App) -> None:
    """Update an existing app in the list.
    
    Args:
        app: App object with updated data.
    """
    apps = load_apps()
    
    for i, existing_app in enumerate(apps):
        if existing_app.id == app.id:
            apps[i] = app
            break
    
    save_apps(apps)


def delete_app(app_id: str) -> None:
    """Delete an app from the list.
    
    Args:
        app_id: ID of the app to delete.
    """
    apps = load_apps()
    apps = [app for app in apps if app.id != app_id]
    save_apps(apps)


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


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers.
    
    Args:
        version: Version string (e.g., "1.2.3").
        
    Returns:
        Tuple of integers (e.g., (1, 2, 3)).
    """
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
        Normalized version string.
    """
    if not version:
        return None
    
    version = version.strip()
    
    if version.lower().startswith("v"):
        version = version[1:]
    
    return version if version else None