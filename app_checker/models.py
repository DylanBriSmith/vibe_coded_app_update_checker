"""Data models for App Update Checker."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, cast
import uuid


class AppSource(Enum):
    WINGET = "winget"
    GITHUB = "github"
    CUSTOM = "custom"
    HOMEBREW = "homebrew"


class AppStatus(Enum):
    OK = "ok"
    UPDATE_AVAILABLE = "update"
    CHECKING = "checking"
    ERROR = "error"
    IGNORED = "ignored"
    UNKNOWN = "unknown"


@dataclass
class App:
    id: str = field(default="")
    name: str = ""
    source: AppSource = field(default=AppSource.CUSTOM)
    installed_version: Optional[str] = None
    latest_version: Optional[str] = None
    ignored: bool = False
    last_checked: Optional[str] = None
    last_error: Optional[str] = None
    release_url: Optional[str] = None
    added_at: Optional[str] = None
    
    winget_id: Optional[str] = None
    github_repo: Optional[str] = None
    custom_url: Optional[str] = None
    version_regex: Optional[str] = None
    homebrew_formula: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.added_at is None:
            self.added_at = datetime.now().isoformat()

    @property
    def status(self) -> AppStatus:
        if self.ignored:
            return AppStatus.IGNORED
        if self.last_error:
            return AppStatus.ERROR
        if self.latest_version is None:
            return AppStatus.UNKNOWN
        if self.installed_version is None:
            return AppStatus.UNKNOWN
        if self.latest_version != self.installed_version:
            return AppStatus.UPDATE_AVAILABLE
        return AppStatus.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source.value,
            "installed_version": self.installed_version,
            "latest_version": self.latest_version,
            "ignored": self.ignored,
            "last_checked": self.last_checked,
            "last_error": self.last_error,
            "release_url": self.release_url,
            "added_at": self.added_at,
            "winget_id": self.winget_id,
            "github_repo": self.github_repo,
            "custom_url": self.custom_url,
            "version_regex": self.version_regex,
            "homebrew_formula": self.homebrew_formula,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "App":
        source_raw = data.get("source", "custom")
        if isinstance(source_raw, str):
            try:
                source = AppSource(source_raw)
            except ValueError:
                source = AppSource.CUSTOM
        else:
            source = AppSource.CUSTOM

        def _get_str(key: str) -> Optional[str]:
            val = data.get(key)
            if isinstance(val, str):
                return val
            return None

        def _get_bool(key: str, default: bool = False) -> bool:
            val = data.get(key)
            if isinstance(val, bool):
                return val
            return default

        return cls(
            id=_get_str("id") or str(uuid.uuid4()),
            name=_get_str("name") or "",
            source=source,
            installed_version=_get_str("installed_version"),
            latest_version=_get_str("latest_version"),
            ignored=_get_bool("ignored", False),
            last_checked=_get_str("last_checked"),
            last_error=_get_str("last_error"),
            release_url=_get_str("release_url"),
            added_at=_get_str("added_at"),
            winget_id=_get_str("winget_id"),
            github_repo=_get_str("github_repo"),
            custom_url=_get_str("custom_url"),
            version_regex=_get_str("version_regex"),
            homebrew_formula=_get_str("homebrew_formula"),
        )


@dataclass
class UpdateInfo:
    latest_version: Optional[str] = None
    release_url: Optional[str] = None
    error: Optional[str] = None
    installed_version: Optional[str] = None