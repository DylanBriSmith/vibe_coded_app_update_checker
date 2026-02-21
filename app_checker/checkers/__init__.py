"""Update checkers for different sources."""

from typing import Type

from ..models import AppSource
from .base import BaseChecker
from .winget import WingetChecker
from .github import GitHubChecker
from .custom import CustomChecker
from .homebrew import HomebrewChecker

__all__ = [
    "BaseChecker",
    "WingetChecker",
    "GitHubChecker",
    "CustomChecker",
    "HomebrewChecker",
    "CheckerRegistry",
    "get_checker",
]


class CheckerRegistry:
    """Registry for update checkers."""
    
    _checkers: dict[AppSource, Type[BaseChecker]] = {}
    
    @classmethod
    def register(cls, source: AppSource, checker_class: Type[BaseChecker]) -> None:
        """Register a checker for a source type.
        
        Args:
            source: The app source type.
            checker_class: The checker class to register.
        """
        cls._checkers[source] = checker_class
    
    @classmethod
    def get_checker_class(cls, source: AppSource) -> Type[BaseChecker] | None:
        """Get the checker class for a source type.
        
        Args:
            source: The app source type.
            
        Returns:
            The checker class, or None if not registered.
        """
        return cls._checkers.get(source)
    
    @classmethod
    def create_checker(cls, source: AppSource) -> BaseChecker | None:
        """Create a checker instance for a source type.
        
        Args:
            source: The app source type.
            
        Returns:
            A new checker instance, or None if not registered.
        """
        checker_class = cls.get_checker_class(source)
        if checker_class:
            return checker_class()
        return None
    
    @classmethod
    def registered_sources(cls) -> list[AppSource]:
        """Get list of registered source types.
        
        Returns:
            List of registered AppSource values.
        """
        return list(cls._checkers.keys())


CheckerRegistry.register(AppSource.WINGET, WingetChecker)
CheckerRegistry.register(AppSource.GITHUB, GitHubChecker)
CheckerRegistry.register(AppSource.CUSTOM, CustomChecker)
CheckerRegistry.register(AppSource.HOMEBREW, HomebrewChecker)


def get_checker(source: AppSource) -> BaseChecker | None:
    """Get a checker instance for a source type.
    
    Args:
        source: The app source type.
        
    Returns:
        A new checker instance, or None if not registered.
    """
    return CheckerRegistry.create_checker(source)