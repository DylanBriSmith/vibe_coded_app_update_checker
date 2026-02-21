# Knowledge Base - App Update Checker

This document captures all architectural decisions, patterns, and implementation details for future reference.

---

## Project Overview

A TUI application to check for updates to installed applications. No auto-updating - just see what's available.

**Key Features:**
- Multiple update sources: Winget, GitHub Releases, Custom URLs
- Interactive TUI with Textual
- CLI for scripting
- Concurrent update checks
- Smart scanning (winget auto-add, interactive for non-winget)

---

## Architecture Decisions

### 1. Strategy Pattern for Checkers
Each update source implements `BaseChecker`:
- `checkers/winget.py` - Windows Package Manager
- `checkers/github.py` - GitHub Releases API
- `checkers/custom.py` - Custom URL + regex

**To add a new source:**
1. Add enum to `AppSource` in `models.py`
2. Create `checkers/<source>.py` inheriting from `BaseChecker`
3. Register in `checkers/__init__.py`
4. Update TUI `AddAppScreen` with new source options

### 2. Service Layer Pattern
`UpdateService` provides high-level API:
- Concurrency control via `asyncio.Semaphore`
- Checker caching
- Progress callbacks for CLI

### 3. Message-Based TUI
Widgets post messages, screens handle with `@on()` decorator:
```python
@on(AppTable.AppSelected)
def on_app_selected(self, event: AppTable.AppSelected) -> None:
    ...
```

### 4. Global State for Data Directory
```python
# utils.py
_data_dir: Optional[Path] = None

def set_data_dir(path: Path) -> None:
    global _data_dir
    _data_dir = path

def get_data_dir() -> Path:
    return _data_dir if _data_dir is not None else DEFAULT_DATA_DIR
```

---

## Implementation Details

### Scan Feature (Added Feb 2026)

**CLI Scan Modes:**
```bash
python -m app_checker scan                    # Auto-add winget apps only
python -m app_checker scan --interactive      # Prompt for non-winget apps
python -m app_checker scan --all              # Legacy: add all as winget
```

**TUI Scan:**
- Press `S` to open ScanScreen modal
- Shows found apps grouped by source
- Auto-adds winget source apps
- Non-winget apps require manual setup via CLI `--interactive`

**Implementation:**
- `WingetChecker._parse_winget_list_output()` now captures actual source (winget, msstore, etc.)
- `_interactive_scan()` handles GitHub search and Custom URL prompts
- `_handle_github_search()` uses `GitHubChecker.search_repo()` to find repos

### Concurrent Checking

Both CLI and TUI use `asyncio.gather()` with semaphore (max 5):

```python
semaphore = asyncio.Semaphore(5)

async def check_one(app: App, index: int) -> None:
    async with semaphore:
        info = await checker_app.check_app(app)
        # Update app and refresh UI
        
tasks = [check_one(app, i) for i, app in enumerate(apps) if not app.ignored]
await asyncio.gather(*tasks)
```

### Type Casting in TUI

Textual's `App` class conflicts with project's `UpdateCheckerApp`:

```python
from typing import cast
from .app import UpdateCheckerApp

checker_app = cast(UpdateCheckerApp, self.app)
```

---

## Code Patterns

### Adding a New Checker

```python
# checkers/newsource.py
from .base import BaseChecker
from ..models import App, AppSource, UpdateInfo

class NewSourceChecker(BaseChecker):
    @property
    def source_type(self) -> str:
        return "newsource"
    
    def can_check(self, app: App) -> bool:
        return app.source == AppSource.NEWSOURCE
    
    async def check(self, app: App) -> UpdateInfo:
        # Fetch version info
        return UpdateInfo(
            latest_version=version,
            release_url=url,
            installed_version=app.installed_version
        )

# checkers/__init__.py
CheckerRegistry.register(AppSource.NEWSOURCE, NewSourceChecker)
```

### Adding TUI Functionality

1. Add keybinding to `BINDINGS`:
```python
BINDINGS = [("x", "new_action", "New Action")]
```

2. Create action method:
```python
def action_new_action(self) -> None:
    # Do something
```

3. If widget-based, post message and handle:
```python
# In widget
self.post_message(self.MyMessage(data))

# In screen
@on(Widget.MyMessage)
def on_my_message(self, event: Widget.MyMessage) -> None:
    ...
```

---

## Known Limitations

1. **No auto-update** - Only checks, doesn't install updates
2. **No tests** - No automated test suite
3. **Simple version comparison** - Uses tuple comparison, may not handle all semver cases
4. **HTTP client recreation** - Each request creates new `httpx.AsyncClient` (minor perf issue)

---

## File Structure

```
app_checker/
├── __init__.py           # Package init, version
├── __main__.py           # Entry point for python -m
├── main.py               # CLI entry point, argparse, scan, export/import
├── models.py             # App, UpdateInfo, AppSource, AppStatus
├── service.py            # UpdateService (business logic)
├── utils.py              # load_apps, save_apps, set_data_dir
├── constants.py          # Timeouts, limits, patterns
├── logging_config.py     # Logging setup
├── notifications.py      # Cross-platform desktop notifications
├── checkers/
│   ├── __init__.py       # CheckerRegistry
│   ├── base.py           # BaseChecker (abstract)
│   ├── winget.py         # Windows Package Manager
│   ├── github.py         # GitHub Releases API
│   ├── custom.py         # Custom URL + regex
│   └── homebrew.py       # Homebrew (macOS)
└── tui/
    ├── __init__.py
    ├── app.py            # UpdateCheckerApp
    ├── screens.py        # MainScreen, AddAppScreen, ScanScreen, DetailScreen
    ├── widgets.py        # AppTable, StatusBar, AppDetail
    └── styles.tcss       # External CSS
├── constants.py          # MAX_CONCURRENT_CHECKS, timeouts, etc.
├── logging_config.py     # Logging setup
├── checkers/
│   ├── __init__.py       # CheckerRegistry, get_checker()
│   ├── base.py           # BaseChecker (abstract)
│   ├── winget.py         # WingetChecker + scan_installed_apps()
│   ├── github.py         # GitHubChecker + validate_repo(), search_repo()
│   └── custom.py         # CustomChecker + detect_version_patterns()
└── tui/
    ├── __init__.py
    ├── app.py            # UpdateCheckerApp, service proxy methods
    ├── screens.py        # MainScreen, AddAppScreen, ScanScreen, DetailScreen
    ├── widgets.py        # AppTable, StatusBar, AppDetail
    └── styles.tcss       # External CSS

data/
├── apps.json             # Tracked apps
├── apps.json.bak         # Backup
└── apps.json.example     # Example
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `models.py:26-127` | `App` dataclass with source-specific fields |
| `models.py:49-61` | `App.status` computed property |
| `service.py:52-78` | `check_app()` with semaphore |
| `service.py:80-116` | `check_all_apps()` concurrent with progress |
| `main.py:114-249` | `run_scan()` with interactive mode |
| `main.py:252-290` | `_interactive_scan()`, `_handle_github_search()`, `_handle_custom_url()` |
| `utils.py:16-32` | `set_data_dir()`, `get_data_dir()` |
| `tui/screens.py:88-117` | `_check_all_apps()` concurrent TUI refresh |
| `tui/screens.py:457-574` | `ScanScreen` class |
| `checkers/winget.py:177-202` | `_parse_winget_list_output()` with source detection |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub API token (5000 vs 60 req/hr) |

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `tui` | Interactive TUI (default) |
| `scan` | Auto-add winget apps |
| `scan --interactive` | Prompt for non-winget apps |
| `scan --all` | Legacy: add all as winget |
| `check` | Check for updates |
| `check --json` | JSON output |
| `list` | List tracked apps |
| `add` | Add new app |
| `update` | Update app version |
| `delete` | Delete app |

**Global flags:** `--verbose`, `--log-file`, `--data-dir`

---

## TUI Keybindings

| Key | Action |
|-----|--------|
| `R` | Refresh all apps |
| `A` | Add new app |
| `S` | Scan for installed apps |
| `/` | Focus search input |
| `Esc` | Clear search |
| `I` | Toggle ignore |
| `D` | Delete app |
| `O` | Open release URL |
| `Q` | Quit |

---

## Future Enhancements (Considered but not implemented)

1. **Shared HTTP Client** - Reuse `httpx.AsyncClient` for better connection pooling
2. **Better Version Comparison** - Use `packaging.version` for semver
3. **TUI Interactive Scan** - Full interactive non-winget setup in TUI (currently CLI only)
4. **Test Suite** - Add pytest tests

---

## Session History

### Feb 2026 Session (Part 2)

**New Features Added:**
1. **TUI Search** - Press `/` to filter apps by name, `Esc` to clear
2. **Desktop Notifications** - `check --notify` sends desktop notification
3. **Homebrew Support** - macOS package manager support
   - New `AppSource.HOMEBREW` enum
   - `HomebrewChecker` class in `checkers/homebrew.py`
   - Scan installed formulae and casks
   - Add via CLI: `--source homebrew --homebrew-formula`
   - Add via TUI: Homebrew option in AddAppScreen
4. **Export/Import** - Backup and restore app lists
   - `python -m app_checker export > backup.json`
   - `python -m app_checker import backup.json`
   - `--merge` flag to merge with existing apps

**Files Created:**
- `app_checker/notifications.py` - Cross-platform notifications
- `app_checker/checkers/homebrew.py` - Homebrew checker

**Files Modified:**
- `models.py` - Added `AppSource.HOMEBREW`, `homebrew_formula` field
- `main.py` - Added export/import commands, --notify flag, homebrew support
- `tui/screens.py` - Search input, Homebrew option in AddAppScreen
- `constants.py` - Added `HOMEBREW_TIMEOUT`
- `checkers/__init__.py` - Registered HomebrewChecker
- `requirements.txt` - Added `plyer`
- `AGENTS.md`, `README.md`, `KNOWLEDGE.md` - Updated docs

### Feb 2026 Session (Part 1)

**Changes Made:**
1. Fixed TUI sequential checking → concurrent with semaphore
2. Fixed TUI type errors with `cast(UpdateCheckerApp, self.app)`
3. Fixed `--data-dir` flag (was parsed but never used)
4. Cleaned up unused imports
5. Added type hints to `tui/app.py`
6. Added smart scan feature:
   - CLI: `--interactive` and `--all` flags
   - TUI: `ScanScreen` with `S` keybinding
   - Proper source detection (winget vs msstore vs other)
7. Created AGENTS.md and this KNOWLEDGE.md

**Files Modified:**
- `utils.py` - Added `set_data_dir()`
- `main.py` - Fixed imports, added scan modes
- `tui/screens.py` - Concurrent checking, ScanScreen
- `tui/app.py` - Type hints, ScanScreen registration
- `tui/widgets.py` - `Optional[App]` for `update_app()`
- `checkers/winget.py` - Source detection in scan
- `service.py` - Removed unused import
- `AGENTS.md` - Created and updated
- `README.md` - Updated scan docs
- `KNOWLEDGE.md` - Created (this file)
