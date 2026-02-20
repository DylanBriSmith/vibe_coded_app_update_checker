"""Data models for App Update Checker."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class AppSource(Enum):
    WINGET = "winget"
    GITHUB = "github"
    CUSTOM = "custom"


class AppStatus(Enum):
    OK = "ok"
    UPDATE_AVAILABLE = "update"
    CHECKING = "checking"
    ERROR = "error"
    IGNORED = "ignored"
    UNKNOWN = "unknown"


@dataclass
class App:
    id: str
    name: str
    source: AppSource
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

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.added_at:
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

    def to_dict(self) -> dict:
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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "App":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            source=AppSource(data["source"]),
            installed_version=data.get("installed_version"),
            latest_version=data.get("latest_version"),
            ignored=data.get("ignored", False),
            last_checked=data.get("last_checked"),
            last_error=data.get("last_error"),
            release_url=data.get("release_url"),
            added_at=data.get("added_at"),
            winget_id=data.get("winget_id"),
            github_repo=data.get("github_repo"),
            custom_url=data.get("custom_url"),
            version_regex=data.get("version_regex"),
        )


@dataclass
class UpdateInfo:
    latest_version: Optional[str]
    release_url: Optional[str] = None
    error: Optional[str] = None
    installed_version: Optional[str] = None