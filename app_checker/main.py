"""Entry point for App Update Checker."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Optional

from .models import App, AppSource
from .checkers import WingetChecker, GitHubChecker, CustomChecker
from .utils import (
    add_app,
    load_apps,
    save_apps,
    ensure_data_dir,
)
from .tui import UpdateCheckerApp


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check for updates to installed applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    tui_parser = subparsers.add_parser("tui", help="Run interactive TUI (default)")
    tui_parser.set_defaults(func=run_tui)

    scan_parser = subparsers.add_parser("scan", help="Scan for installed apps")
    scan_parser.set_defaults(func=run_scan)

    check_parser = subparsers.add_parser("check", help="Check for updates (non-interactive)")
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
    list_parser.set_defaults(func=run_list)

    args = parser.parse_args()

    ensure_data_dir()

    if args.command is None:
        run_tui()
    elif hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


def run_tui():
    """Run the interactive TUI."""
    app = UpdateCheckerApp()
    app.run()


def run_scan(args):
    """Scan for installed apps using winget."""
    print("Scanning for installed applications...")
    
    checker = WingetChecker()
    apps = asyncio.run(checker.scan_installed_apps())

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


def run_check(args):
    """Check for updates (non-interactive)."""
    apps = load_apps()

    if not apps:
        print("No apps configured. Run 'app-checker scan' first or add apps manually.")
        return

    print(f"Checking {len(apps)} apps for updates...\n")

    winget_checker = WingetChecker()
    github_checker = GitHubChecker()
    custom_checker = CustomChecker()

    updates_available = []

    async def check_all():
        for app in apps:
            if app.ignored:
                continue

            print(f"  Checking {app.name}...", end=" ")

            if app.source == AppSource.WINGET:
                info = await winget_checker.check(app)
            elif app.source == AppSource.GITHUB:
                info = await github_checker.check(app)
            elif app.source == AppSource.CUSTOM:
                info = await custom_checker.check(app)
            else:
                info = None

            if info:
                app.latest_version = info.latest_version
                app.release_url = info.release_url
                app.last_error = info.error
                app.last_checked = datetime.now().isoformat()

                if info.error:
                    print(f"[ERROR] {info.error}")
                elif info.latest_version:
                    if app.installed_version and info.latest_version != app.installed_version:
                        print(f"[UPDATE] {app.installed_version} -> {info.latest_version}")
                        updates_available.append(app)
                    else:
                        print(f"[OK] {info.latest_version}")
                else:
                    print("[UNKNOWN]")
            else:
                print("[ERROR] Could not check")

        save_apps(apps)

    asyncio.run(check_all())

    print(f"\n{'='*50}")
    if updates_available:
        print(f"\n{len(updates_available)} updates available:\n")
        for app in updates_available:
            print(f"  • {app.name}: {app.installed_version} -> {app.latest_version}")
            if app.release_url:
                print(f"    {app.release_url}")
    else:
        print("\nAll apps are up to date!")


def run_add(args):
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


def run_list(args):
    """List tracked apps."""
    apps = load_apps()

    if not apps:
        print("No apps configured.")
        return

    print(f"\nTracked applications ({len(apps)}):\n")
    print(f"{'Name':<30} {'Source':<10} {'Installed':<15} {'Latest':<15} {'Status':<10}")
    print("-" * 80)

    for app in apps:
        status = app.status.value
        installed = app.installed_version or "unknown"
        latest = app.latest_version or "unknown"

        print(f"{app.name[:28]:<30} {app.source.value:<10} {installed:<15} {latest:<15} {status:<10}")

    print()


if __name__ == "__main__":
    main()