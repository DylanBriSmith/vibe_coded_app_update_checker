# App Update Checker

A TUI application to check for updates to installed applications. No auto-updating - just see what's available.

## Features

- **Multiple update sources**: Winget (Windows), GitHub Releases, Custom URLs
- **Interactive TUI**: Browse, filter, and manage tracked apps
- **Auto-detect installed apps**: Scan Windows systems with `winget`
- **Non-interactive mode**: CLI commands for scripting

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
| `I` | Toggle ignore |
| `D` | Delete app |
| `O` | Open release URL |
| `Q` | Quit |

### CLI Commands

```bash
# Scan for installed apps (Windows only, requires winget)
python -m app_checker scan

# Check for updates (non-interactive)
python -m app_checker check

# List tracked apps
python -m app_checker list

# Add apps manually
python -m app_checker add --name "Obsidian" --source github --github-repo "obsidianmd/obsidian-releases"
python -m app_checker add --name "7-Zip" --source custom --url "https://www.7-zip.org/download.html" --regex "7-Zip (\d+\.\d+)"
python -m app_checker add --name "VS Code" --source winget --winget-id "Microsoft.VisualStudioCode"
```

## Source Types

| Source | Description | Required Fields |
|--------|-------------|-----------------|
| `winget` | Windows Package Manager | `--winget-id` |
| `github` | GitHub Releases API | `--github-repo owner/repo` |
| `custom` | Custom URL with regex | `--url`, optionally `--regex` |

### Custom URL Auto-Detection

When using the TUI to add a custom URL app, the tool can auto-detect version patterns from the page.

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
  ]
}
```

## Tech Stack

- Python 3.12+
- [Textual](https://github.com/Textualize/textual) - TUI framework
- httpx - Async HTTP client
- Rich - Terminal formatting

## License

MIT