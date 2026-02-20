"""Base checker abstract class."""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import App, UpdateInfo


class BaseChecker(ABC):
    """Abstract base class for update checkers."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type this checker handles."""
        pass

    @abstractmethod
    async def check(self, app: App) -> UpdateInfo:
        """Check for updates for the given app.
        
        Args:
            app: The app to check for updates.
            
        Returns:
            UpdateInfo with latest version and release URL.
        """
        pass

    def can_check(self, app: App) -> bool:
        """Check if this checker can handle the given app.
        
        Args:
            app: The app to check.
            
        Returns:
            True if this checker can handle the app.
        """
        return app.source.value == self.source_type