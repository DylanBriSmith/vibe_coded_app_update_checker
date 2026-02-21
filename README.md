# App Update Checker

A TUI application to check for updates to installed applications. No auto-updating - just see what's available.

## Features

- **Multiple update sources**: Winget (Windows), Homebrew (macOS), GitHub Releases, Custom URLs
- **Interactive TUI**: Browse, filter, search, and manage tracked apps
- **Smart scanning**: Auto-add winget/homebrew apps, interactive setup for others
- **Desktop notifications**: Get notified when updates are available
- **Cross-platform**: Windows (winget) and macOS (Homebrew) support
- **Non-interactive mode**: CLI commands for scripting
- **Export/Import**: Backup and restore your app list
- **Concurrent checking**: Parallel update checks with configurable concurrency
- **GitHub API token support**: Higher rate limits (5000 vs 60 req/hr)
- **Data backup**: Automatic backup before overwriting data
- **JSON output**: Script-friendly output for automation

## Installation

```bash
git clone https://github.com/DylanBriSmith/vibe_coded_app_update_checker.git
cd vibe_coded_app_update_checker
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Interactive TUI

```bash
python -m app_checker
```

**Keyboard shortcuts:**
| Key | Action |
|-----|--------|
| `R` | Refresh all apps |
| `A` | Add new app |
| `S` | Scan for installed apps |
| `/` | Search/filter apps |
| `Esc` | Clear search |
| `I` | Toggle ignore |
| `D` | Delete app |
| `O` | Open release URL |
| `Q` | Quit |

### CLI Commands

```bash
# Scan for installed apps
python -m app_checker scan                    # Auto-add winget/homebrew apps
python -m app_checker scan --interactive      # Prompt for non-native apps
python -m app_checker scan --all              # Legacy: add all as winget source

# Check for updates
python -m app_checker check                   # Check for updates
python -m app_checker check --notify          # Send desktop notification
python -m app_checker check --json            # JSON output for scripting

# List tracked apps
python -m app_checker list
python -m app_checker list --json

# Add apps manually
python -m app_checker add --name "Obsidian" --source github --github-repo "obsidianmd/obsidian-releases"
python -m app_checker add --name "wget" --source homebrew --homebrew-formula "wget"
python -m app_checker add --name "7-Zip" --source custom --url "https://www.7-zip.org/download.html" --regex "7-Zip (\d+\.\d+)"

# Update app version
python -m app_checker update --id <app-id> --installed-version "16.0.0"

# Delete an app
python -m app_checker delete --id <app-id>

# Export/Import
python -m app_checker export > backup.json    # Export to stdout
python -m app_checker export -f backup.json   # Export to file
python -m app_checker import backup.json      # Import (replaces existing)
python -m app_checker import backup.json --merge # Merge with existing
```

## Source Types

| Source | Description | Required Fields |
|--------|-------------|-----------------|
| `winget` | Windows Package Manager | `--winget-id` |
| `homebrew` | Homebrew (macOS) | `--homebrew-formula` |
| `github` | GitHub Releases API | `--github-repo owner/repo` |
| `custom` | Custom URL with regex | `--url`, optionally `--regex` |

### Custom URL Auto-Detection

When using the TUI to add a custom URL app, the tool can auto-detect version patterns from the page.

## GitHub API Token

For higher rate limits, set the `GITHUB_TOKEN` environment variable:

```bash
export GITHUB_TOKEN=your_github_token
python -m app_checker check
```

Without a token, GitHub API is limited to 60 requests/hour. With a token, it's 5000 requests/hour.

## Data Storage

Apps are stored in `data/apps.json`:

```json
{
  "apps": [
    {
      "id": "uuid",
      "name": "7-Zip",
      "source": "custom",
      "installed_version": "25.01",
      "latest_version": "26.00",
      "custom_url": "https://www.7-zip.org/download.html",
      "version_regex": "7-Zip (\\d+\\.\\d+)",
      "ignored": false
    }
  ],
  "last_updated": "2026-02-20T12:00:00"
}
```

A backup is automatically created at `data/apps.json.bak` before each save.

## Tech Stack

- Python 3.12+
- [Textual](https://github.com/Textualize/textual) - TUI framework
- httpx - Async HTTP client
- Rich - Terminal formatting

## Architecture

```
app_checker/
├── main.py              # CLI entry point
├── models.py            # Data models (App, UpdateInfo)
├── service.py           # Business logic layer
├── utils.py             # Storage utilities
├── constants.py         # Configuration constants
├── logging_config.py    # Logging setup
├── checkers/            # Update source checkers
│   ├── base.py          # Abstract base checker
│   ├── winget.py        # Windows Package Manager
│   ├── github.py        # GitHub Releases API
│   └── custom.py        # Custom URL + regex
└── tui/                 # Terminal UI
    ├── app.py           # Textual application
    ├── screens.py       # Screen definitions
    ├── widgets.py       # Custom widgets
    └── styles.tcss      # External CSS
```

## License

MIT