# AGENTS.md

Guidance for AI agents working in this repository.

## Project Overview

A TUI application to check for updates to installed applications. No auto-updating - just see what's available.

**Key Features:**
- Multiple update sources: Winget, GitHub Releases, Custom URLs
- Interactive TUI with Textual
- CLI for scripting
- Concurrent update checks
- GitHub API token support for higher rate limits

## Tech Stack

- Python 3.12+
- Textual (TUI framework)
- httpx (async HTTP client)
- Rich (terminal formatting)

## Quick Reference Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Interactive TUI (default)
python -m app_checker

# CLI Commands
python -m app_checker scan                    # Auto-add winget apps only
python -m app_checker scan --interactive     # Prompt for non-winget apps
python -m app_checker scan --all             # Legacy: add all as winget source
python -m app_checker check                   # Check for updates
python -m app_checker check --notify          # Send desktop notification
python -m app_checker check --json            # JSON output for scripting
python -m app_checker list                    # List tracked apps
python -m app_checker add --name "App" --source github --github-repo "owner/repo"
python -m app_checker add --name "App" --source homebrew --homebrew-formula "wget"
python -m app_checker update --id <uuid> --installed-version "1.0.0"
python -m app_checker delete --id <uuid>
python -m app_checker export                  # Export apps to JSON
python -m app_checker import apps.json        # Import apps (replaces existing)
python -m app_checker import apps.json --merge # Merge with existing apps

# Verbose logging
python -m app_checker --verbose check
python -m app_checker --log-file app.log check
```

## Architecture

```
app_checker/
├── __init__.py           # Package init, version
├── __main__.py           # Entry point for python -m
├── main.py               # CLI entry point, argparse
├── models.py             # Data models (App, UpdateInfo, enums)
├── service.py            # Business logic layer (UpdateService)
├── utils.py              # Storage utilities (load/save apps)
├── constants.py          # Configuration constants
├── logging_config.py     # Logging setup
├── notifications.py      # Cross-platform desktop notifications
├── checkers/             # Update source checkers (Strategy pattern)
│   ├── __init__.py       # CheckerRegistry
│   ├── base.py           # BaseChecker (abstract)
│   ├── winget.py         # Windows Package Manager
│   ├── github.py         # GitHub Releases API
│   ├── custom.py         # Custom URL + regex
│   └── homebrew.py       # Homebrew (macOS)
└── tui/                  # Terminal UI (Textual)
    ├── __init__.py
    ├── app.py            # UpdateCheckerApp
    ├── screens.py        # MainScreen, AddAppScreen, ScanScreen, DetailScreen
    ├── widgets.py        # AppTable, StatusBar, AppDetail
    └── styles.tcss       # External CSS

data/
├── apps.json             # Tracked apps data
├── apps.json.bak         # Automatic backup
└── apps.json.example     # Example data
```

## Checker Pattern (Strategy)

Update sources use the Strategy pattern via `BaseChecker`:

1. **Add a new checker:**
   - Create `checkers/<source>.py`
   - Inherit from `BaseChecker`
   - Implement `source_type`, `check(app)`, and optionally `can_check(app)`
   - Register in `checkers/__init__.py`: `CheckerRegistry.register(AppSource.<TYPE>, NewChecker)`

2. **BaseChecker interface:**
   ```python
   class BaseChecker(ABC):
       @property
       @abstractmethod
       def source_type(self) -> str: ...
       
       @abstractmethod
       async def check(self, app: App) -> UpdateInfo: ...
       
       def can_check(self, app: App) -> bool: ...  # Optional override
   ```

3. **Example:**
   - See `checkers/github.py` for GitHub API implementation
   - See `checkers/custom.py` for URL + regex implementation

## Data Models

### App (models.py)
Core dataclass for tracked applications:
- `id`, `name`, `source` (AppSource enum)
- `installed_version`, `latest_version`
- `ignored`, `last_checked`, `last_error`, `release_url`
- Source-specific: `winget_id`, `github_repo`, `custom_url`, `version_regex`

### AppSource Enum
- `WINGET` - Windows Package Manager
- `GITHUB` - GitHub Releases API
- `CUSTOM` - Custom URL + regex

### AppStatus Enum (computed property)
- `OK` - Up to date
- `UPDATE_AVAILABLE` - Newer version exists
- `CHECKING` - Currently being checked
- `ERROR` - Check failed
- `IGNORED` - User marked as ignored
- `UNKNOWN` - Not enough info

### UpdateInfo
Result from checker: `latest_version`, `release_url`, `error`, `installed_version`

### Utility Functions (utils.py)
- `set_data_dir(path)` - Override default data directory
- `get_data_dir()` - Get current data directory path
- `load_apps()` / `save_apps(apps)` - Persist app data to JSON
- `add_app(app)` / `update_app(app)` / `delete_app(id)` - CRUD operations

## CLI Reference

| Command | Description |
|---------|-------------|
| `tui` | Interactive TUI (default) |
| `scan` | Scan for installed apps (Windows/macOS) |
| `check` | Check for updates (non-interactive) |
| `list` | List tracked apps |
| `add` | Add a new app |
| `update` | Update app's installed version |
| `delete` | Delete an app |
| `export` | Export app list to JSON |
| `import` | Import apps from JSON |

**Scan modes:**
- `scan` - Auto-add only apps from winget/homebrew source
- `scan --interactive` - Prompt to configure non-winget apps (GitHub/Custom URL)
- `scan --all` - Legacy mode: add all apps as winget source

**Check options:**
- `check --json` - Output as JSON for scripting
- `check --notify` - Send desktop notification with results

**Global flags:** `--verbose`, `--log-file`, `--data-dir`

## TUI Reference

### Screens
- **MainScreen** - App table with detail panel
- **AddAppScreen** - Modal for adding new apps
- **ScanScreen** - Modal for scanning installed apps
- **DetailScreen** - Modal with full app info

### Keybindings (MainScreen)
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

### Widgets
- `AppTable` - DataTable with app list, posts messages on actions
- `StatusBar` - Shows totals and last scan time
- `AppDetail` - Right panel with selected app details

### Search
Press `/` to focus the search input, then type to filter apps by name. Press `Esc` to clear the search.

### Concurrency
Both CLI and TUI use concurrent checking (max 5 parallel requests) via `asyncio.gather()` with a semaphore. This is defined in `constants.MAX_CONCURRENT_CHECKS`.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub API token for higher rate limits (5000 vs 60 req/hr) |

## Data Storage

Apps stored in `data/apps.json`:
```json
{
  "apps": [
    {
      "id": "uuid",
      "name": "App Name",
      "source": "github",
      "installed_version": "1.0.0",
      "latest_version": "2.0.0",
      "ignored": false,
      "github_repo": "owner/repo",
      ...
    }
  ],
  "last_updated": "ISO timestamp"
}
```

**Backup behavior:**
- Automatic backup to `data/apps.json.bak` before each save
- Atomic writes via temp file
- Auto-restore from backup if JSON corrupted

## Common Tasks

### Add a new update source
1. Add enum value to `AppSource` in `models.py`
2. Create `checkers/<source>.py` inheriting from `BaseChecker`
3. Register in `checkers/__init__.py`
4. Add source-specific fields to `App` model if needed
5. Update TUI `AddAppScreen` with new source options

### Add TUI functionality
1. Add keybinding to screen's `BINDINGS`
2. Create `action_<name>()` method
3. Post message from widget if needed
4. Handle message in screen with `@on(Widget.MessageClass)`

### Extend CLI
1. Add subparser in `main.py`
2. Add arguments to subparser
3. Create `run_<command>(args)` function
4. Set `parser.set_defaults(func=run_command)`

## Testing

Currently no automated tests. Manual testing:
```bash
python -m app_checker          # Test TUI
python -m app_checker check    # Test update checking
python -m app_checker list     # Test listing
```

## Known Limitations

1. **Winget only on Windows** - Winget checker only works on Windows with winget installed
2. **No auto-update** - Only checks for updates, doesn't install them
3. **No tests** - No automated test suite
4. **Simple version comparison** - Uses tuple comparison, may not handle all semver cases
5. **No search in TUI** - Search binding defined but not implemented

## Code Style

- **Type hints**: Required on all functions/methods
- **Imports**: `from typing import ...` for typing imports, `cast` for type assertions
- **Type casting**: Use `cast(UpdateCheckerApp, self.app)` when Textual's `App` type conflicts
- **Async patterns**: Use `asyncio.Semaphore` for concurrency control
- **Optional handling**: Use `Optional[T]` for nullable parameters/returns
- **Dict typing**: Use `dict[str, Any]` when values have mixed types (e.g., JSON data)

## Notes for AI Agents

1. **Follow the Strategy pattern** - New checkers inherit from `BaseChecker`
2. **Use type hints** - Project uses Python 3.12+ type hints throughout
3. **Async throughout** - All network operations are async
4. **Message-based TUI** - Widgets post messages, screens handle with `@on()`
5. **Atomic saves** - Always use `save_apps()` for data persistence
6. **Log appropriately** - Use `get_logger(__name__)` for logging
7. **Check `can_check()`** - Before calling checker on an app
8. **TUI type casting** - Use `cast(UpdateCheckerApp, self.app)` in screens to avoid Textual's `App` type conflict

## Version

Current: `0.2.0` (defined in `constants.py`)