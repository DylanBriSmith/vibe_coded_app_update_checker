"""Entry point for App Update Checker."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_DATA_DIR
from .logging_config import get_logger, setup_logging
from .models import App, AppSource
from .service import get_service
from .utils import add_app, ensure_data_dir, is_update_available, load_apps, save_apps

logger = get_logger(__name__)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check for updates to installed applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--verbose", "-V",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log file path",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Data directory path",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    tui_parser = subparsers.add_parser("tui", help="Run interactive TUI (default)")
    tui_parser.set_defaults(func=run_tui)

    scan_parser = subparsers.add_parser("scan", help="Scan for installed apps")
    scan_parser.set_defaults(func=run_scan)

    check_parser = subparsers.add_parser("check", help="Check for updates (non-interactive)")
    check_parser.add_argument("--json", action="store_true", help="Output as JSON")
    check_parser.set_defaults(func=run_check)

    add_parser = subparsers.add_parser("add", help="Add a new app to track")
    add_parser.add_argument("--name", "-n", required=True, help="App name")
    add_parser.add_argument(
        "--source", "-s",
        choices=["winget", "github", "custom"],
        required=True,
        help="Source type"
    )
    add_parser.add_argument("--installed-version", "-v", help="Currently installed version (optional)")
    add_parser.add_argument("--winget-id", help="Winget package ID")
    add_parser.add_argument("--github-repo", help="GitHub repository (owner/repo)")
    add_parser.add_argument("--url", help="Custom URL for version checking")
    add_parser.add_argument("--regex", help="Regex pattern for version extraction")
    add_parser.set_defaults(func=run_add)

    list_parser = subparsers.add_parser("list", help="List tracked apps")
    list_parser.add_argument("--json", action="store_true", help="Output as JSON")
    list_parser.set_defaults(func=run_list)

    update_parser = subparsers.add_parser("update", help="Update app version")
    update_parser.add_argument("--id", required=True, help="App ID")
    update_parser.add_argument("--installed-version", "-v", required=True, help="New installed version")
    update_parser.set_defaults(func=run_update)

    delete_parser = subparsers.add_parser("delete", help="Delete an app")
    delete_parser.add_argument("--id", required=True, help="App ID")
    delete_parser.set_defaults(func=run_delete)

    args = parser.parse_args()

    log_level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    setup_logging(level=log_level, log_file=getattr(args, "log_file", None))

    ensure_data_dir()

    if args.command is None:
        run_tui()
    elif hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


def run_tui(args=None) -> None:
    """Run the interactive TUI."""
    from .tui import UpdateCheckerApp
    
    logger.debug("Starting TUI")
    app = UpdateCheckerApp()
    app.run()


def run_scan(args) -> None:
    """Scan for installed apps using winget."""
    print("Scanning for installed applications...")
    
    service = get_service()
    apps = asyncio.run(service.scan_installed_apps())

    if not apps:
        print("No apps found or winget not available.")
        return

    print(f"\nFound {len(apps)} installed applications:\n")

    existing_apps = load_apps()
    existing_ids = {app.winget_id for app in existing_apps if app.winget_id}

    new_count = 0
    for app_data in apps:
        winget_id = app_data.get("winget_id", "")
        is_new = winget_id not in existing_ids

        if is_new:
            new_app = App(
                name=app_data["name"],
                source=AppSource.WINGET,
                installed_version=app_data.get("installed_version"),
                winget_id=winget_id,
            )
            add_app(new_app)
            new_count += 1
            status = "[NEW]"
        else:
            status = "[EXISTS]"

        print(f"  {status} {app_data['name']} ({winget_id}) - v{app_data.get('installed_version', 'unknown')}")

    print(f"\nAdded {new_count} new apps to tracking.")
    logger.info("Scan complete: %d apps found, %d new", len(apps), new_count)


def run_check(args) -> None:
    """Check for updates (non-interactive)."""
    apps = load_apps()

    if not apps:
        print("No apps configured. Run 'app-checker scan' first or add apps manually.")
        return

    print(f"Checking {len(apps)} apps for updates...\n")

    service = get_service()
    updates_available: list[App] = []

    def progress_callback(app: App, info, index: int, total: int) -> None:
        if app.ignored:
            return

        if info.error:
            print(f"  [{index}/{total}] {app.name}... [ERROR] {info.error}")
        elif info.latest_version:
            if app.installed_version and info.latest_version != app.installed_version:
                print(f"  [{index}/{total}] {app.name}... [UPDATE] {app.installed_version} -> {info.latest_version}")
                updates_available.append(app)
            else:
                print(f"  [{index}/{total}] {app.name}... [OK] {info.latest_version}")
        else:
            print(f"  [{index}/{total}] {app.name}... [UNKNOWN]")

    async def check_all() -> list[App]:
        return await service.check_and_update(apps)

    asyncio.run(check_all())

    if getattr(args, "json", False):
        import json as json_module
        output = {
            "updates_available": [
                {
                    "name": app.name,
                    "installed_version": app.installed_version,
                    "latest_version": app.latest_version,
                    "release_url": app.release_url,
                }
                for app in updates_available
            ],
            "total_apps": len(apps),
            "updates_count": len(updates_available),
        }
        print(json_module.dumps(output, indent=2))
    else:
        print(f"\n{'='*50}")
        if updates_available:
            print(f"\n{len(updates_available)} updates available:\n")
            for app in updates_available:
                print(f"  • {app.name}: {app.installed_version} -> {app.latest_version}")
                if app.release_url:
                    print(f"    {app.release_url}")
        else:
            print("\nAll apps are up to date!")


def run_add(args) -> None:
    """Add a new app to track."""
    app_data = {
        "name": args.name,
        "source": args.source,
    }

    if args.installed_version:
        app_data["installed_version"] = args.installed_version

    if args.source == "winget":
        if args.winget_id:
            app_data["winget_id"] = args.winget_id
        else:
            print("Error: --winget-id is required for winget source")
            sys.exit(1)

    elif args.source == "github":
        if args.github_repo:
            app_data["github_repo"] = args.github_repo
        else:
            print("Error: --github-repo is required for github source")
            sys.exit(1)

    elif args.source == "custom":
        if args.url:
            app_data["custom_url"] = args.url
        else:
            print("Error: --url is required for custom source")
            sys.exit(1)
        if args.regex:
            app_data["version_regex"] = args.regex

    app = App.from_dict(app_data)
    add_app(app)

    version_info = f" (v{args.installed_version})" if args.installed_version else ""
    print(f"Added '{app.name}'{version_info} to tracking.")
    logger.info("Added app: %s (%s)", app.name, app.source.value)


def run_list(args) -> None:
    """List tracked apps."""
    apps = load_apps()

    if not apps:
        print("No apps configured.")
        return

    if getattr(args, "json", False):
        import json as json_module
        output = {
            "apps": [app.to_dict() for app in apps],
            "count": len(apps),
        }
        print(json_module.dumps(output, indent=2))
    else:
        print(f"\nTracked applications ({len(apps)}):\n")
        print(f"{'Name':<30} {'Source':<10} {'Installed':<15} {'Latest':<15} {'Status':<10}")
        print("-" * 80)

        for app in apps:
            status = app.status.value
            installed = app.installed_version or "unknown"
            latest = app.latest_version or "unknown"

            print(f"{app.name[:28]:<30} {app.source.value:<10} {installed:<15} {latest:<15} {status:<10}")

        print()


def run_update(args) -> None:
    """Update an app's installed version."""
    apps = load_apps()
    
    for app in apps:
        if app.id == args.id:
            app.installed_version = args.installed_version
            save_apps(apps)
            print(f"Updated '{app.name}' to version {args.installed_version}")
            logger.info("Updated app %s to version %s", app.name, args.installed_version)
            return
    
    print(f"Error: App with ID '{args.id}' not found")
    sys.exit(1)


def run_delete(args) -> None:
    """Delete an app."""
    apps = load_apps()
    
    for app in apps:
        if app.id == args.id:
            apps = [a for a in apps if a.id != args.id]
            save_apps(apps)
            print(f"Deleted '{app.name}'")
            logger.info("Deleted app: %s", app.name)
            return
    
    print(f"Error: App with ID '{args.id}' not found")
    sys.exit(1)


if __name__ == "__main__":
    main()