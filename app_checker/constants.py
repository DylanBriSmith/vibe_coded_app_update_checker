"""Constants and configuration for App Update Checker."""

from pathlib import Path

# Version
__version__ = "0.2.0"

# Paths
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
APPS_FILE = "apps.json"
BACKUP_FILE = "apps.json.bak"
CONFIG_FILE = "config.toml"
CSS_FILE = Path(__file__).parent / "tui" / "styles.tcss"

# Timeouts (seconds)
DEFAULT_HTTP_TIMEOUT = 30.0
WINGET_TIMEOUT = 60
WINGET_SEARCH_TIMEOUT = 30
GITHUB_TIMEOUT = 30.0
CUSTOM_URL_TIMEOUT = 30.0

# Limits
MAX_DETECTED_PATTERNS = 5
MAX_SEARCH_RESULTS = 10
MAX_UNIQUE_MATCHES = 5

# GitHub API
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RATE_LIMIT_HEADER = "x-ratelimit-remaining"

# Version parsing patterns
DEFAULT_VERSION_PATTERNS = [
    r"[Vv]ersion[:\s]+(\d+(?:\.\d+)*)",
    r"[Vv](\d+(?:\.\d+)+)",
    r"[Ll]atest[:\s]+(\d+(?:\.\d+)*)",
    r"(\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+)?)",
    r"(\d+\.\d+)",
]

# HTTP Headers
DEFAULT_USER_AGENT = "App-Update-Checker/{} (+https://github.com/DylanBriSmith/vibe_coded_app_update_checker)".format(__version__)

# Concurrent checking
MAX_CONCURRENT_CHECKS = 5