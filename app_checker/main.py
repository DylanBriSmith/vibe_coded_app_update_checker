"""Entry point for App Update Checker."""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .constants import DEFAULT_DATA_DIR
from .logging_config import get_logger, setup_logging
from .models import App, AppSource
from .service import get_service
from .utils import add_app, ensure_data_dir, load_apps, save_apps, set_data_dir

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
    scan_parser.add_argument("--interactive", "-i", action="store_true", 
                             help="Prompt for non-winget apps to configure tracking")
    scan_parser.add_argument("--all", action="store_true",
                             help="Auto-add all apps as winget source (legacy behavior)")
    scan_parser.set_defaults(func=run_scan)

    check_parser = subparsers.add_parser("check", help="Check for updates (non-interactive)")
    check_parser.add_argument("--json", action="store_true", help="Output as JSON")
    check_parser.add_argument("--notify", action="store_true", help="Send desktop notification")
    check_parser.set_defaults(func=run_check)

    add_parser = subparsers.add_parser("add", help="Add a new app to track")
    add_parser.add_argument("--name", "-n", required=True, help="App name")
    add_parser.add_argument(
        "--source", "-s",
        choices=["winget", "github", "custom", "homebrew"],
        required=True,
        help="Source type"
    )
    add_parser.add_argument("--installed-version", "-v", help="Currently installed version (optional)")
    add_parser.add_argument("--winget-id", help="Winget package ID")
    add_parser.add_argument("--github-repo", help="GitHub repository (owner/repo)")
    add_parser.add_argument("--url", help="Custom URL for version checking")
    add_parser.add_argument("--regex", help="Regex pattern for version extraction")
    add_parser.add_argument("--homebrew-formula", help="Homebrew formula name")
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

    export_parser = subparsers.add_parser("export", help="Export app list to JSON")
    export_parser.add_argument("--file", "-f", type=Path, help="Output file (default: stdout)")
    export_parser.set_defaults(func=run_export)

    import_parser = subparsers.add_parser("import", help="Import apps from JSON")
    import_parser.add_argument("file", type=Path, help="JSON file to import")
    import_parser.add_argument("--merge", action="store_true", help="Merge with existing apps (default: replace)")
    import_parser.set_defaults(func=run_import)

    args = parser.parse_args()

    log_level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    setup_logging(level=log_level, log_file=getattr(args, "log_file", None))

    data_dir = getattr(args, "data_dir", DEFAULT_DATA_DIR)
    if data_dir != DEFAULT_DATA_DIR:
        set_data_dir(data_dir)

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

    interactive = getattr(args, "interactive", False)
    all_flag = getattr(args, "all", False)

    existing_apps = load_apps()
    existing_ids = {app.winget_id for app in existing_apps if app.winget_id}

    winget_apps = [a for a in apps if a.get("source") == "winget"]
    non_winget_apps = [a for a in apps if a.get("source") != "winget"]

    print(f"\nFound {len(apps)} installed applications:")
    print(f"  - {len(winget_apps)} from winget")
    print(f"  - {len(non_winget_apps)} from other sources")
    print()

    winget_added = 0
    for app_data in winget_apps:
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
            winget_added += 1
            status = "[NEW]"
        else:
            status = "[EXISTS]"

        print(f"  {status} {app_data['name']} ({winget_id}) - v{app_data.get('installed_version', 'unknown')}")

    non_winget_added = 0
    skipped = 0

    if non_winget_apps:
        if all_flag:
            for app_data in non_winget_apps:
                winget_id = app_data.get("winget_id", "")
                if winget_id and winget_id not in existing_ids:
                    new_app = App(
                        name=app_data["name"],
                        source=AppSource.WINGET,
                        installed_version=app_data.get("installed_version"),
                        winget_id=winget_id,
                    )
                    add_app(new_app)
                    non_winget_added += 1
                    print(f"  [NEW] {app_data['name']} ({winget_id}) - v{app_data.get('installed_version', 'unknown')}")
        elif interactive:
            print(f"\n--- Non-winget apps ({len(non_winget_apps)}) ---")
            non_winget_added = _interactive_scan(non_winget_apps, existing_ids)
        else:
            skipped = len(non_winget_apps)
            print(f"\n  {skipped} non-winget apps skipped (use --interactive to configure)")

    total_added = winget_added + non_winget_added
    print(f"\nAdded {total_added} new apps to tracking.")
    if skipped:
        print(f"Skipped {skipped} non-winget apps.")
    logger.info("Scan complete: %d apps found, %d new", len(apps), total_added)


def _interactive_scan(apps: list, existing_ids: set) -> int:
    """Interactive prompt for configuring non-winget apps.
    
    Args:
        apps: List of app data dicts.
        existing_ids: Set of existing winget IDs.
        
    Returns:
        Number of apps added.
    """
    added = 0
    
    for app_data in apps:
        name = app_data.get("name", "Unknown")
        winget_id = app_data.get("winget_id", "")
        version = app_data.get("installed_version", "unknown")
        source = app_data.get("source", "unknown")
        
        print(f"\n  {name} (source: {source}, version: {version})")
        print("  Configure as:")
        print("    1) GitHub (search for repo)")
        print("    2) Custom URL")
        print("    3) Skip")
        
        try:
            choice = input("  Choice [1-3]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Scan interrupted.")
            return added
        
        if choice == "1":
            added += _handle_github_search(name, version)
        elif choice == "2":
            added += _handle_custom_url(name, version)
        else:
            print("    Skipped.")
    
    return added


def _handle_github_search(name: str, version: str) -> int:
    """Handle GitHub search for an app.
    
    Args:
        name: App name to search for.
        version: Installed version.
        
    Returns:
        1 if added, 0 otherwise.
    """
    from .checkers.github import GitHubChecker
    
    checker = GitHubChecker()
    print(f"    Searching GitHub for '{name}'...")
    
    try:
        results = asyncio.run(checker.search_repo(name))
    except Exception as e:
        print(f"    Search error: {e}")
        return 0
    
    if not results:
        print("    No results found.")
        return 0
    
    print("    Found:")
    for i, r in enumerate(results[:5], 1):
        stars = r.get("stars", 0)
        desc = r.get("description", "")[:50] if r.get("description") else ""
        print(f"      {i}) {r['full_name']} ({stars} stars) {desc}")
    
    try:
        choice = input("    Select [1-5] or Enter to skip: ").strip()
        if not choice:
            return 0
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            selected = results[idx]
            new_app = App(
                name=name,
                source=AppSource.GITHUB,
                installed_version=version,
                github_repo=selected["full_name"],
            )
            add_app(new_app)
            print(f"    Added {name} -> {selected['full_name']}")
            return 1
    except (ValueError, EOFError, KeyboardInterrupt):
        pass
    
    return 0


def _handle_custom_url(name: str, version: str) -> int:
    """Handle custom URL configuration for an app.
    
    Args:
        name: App name.
        version: Installed version.
        
    Returns:
        1 if added, 0 otherwise.
    """
    try:
        url = input("    Enter URL: ").strip()
        if not url:
            print("    Skipped.")
            return 0
        
        regex = input("    Enter version regex (optional, press Enter to auto-detect): ").strip()
        
        new_app = App(
            name=name,
            source=AppSource.CUSTOM,
            installed_version=version,
            custom_url=url,
            version_regex=regex or None,
        )
        add_app(new_app)
        print(f"    Added {name} -> {url}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\n    Skipped.")
        return 0


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

    if getattr(args, "notify", False):
        from .notifications import notify_updates_available, notify_all_up_to_date
        if updates_available:
            notify_updates_available(
                len(updates_available),
                [app.name for app in updates_available]
            )
        else:
            notify_all_up_to_date()


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

    elif args.source == "homebrew":
        if args.homebrew_formula:
            app_data["homebrew_formula"] = args.homebrew_formula
        else:
            print("Error: --homebrew-formula is required for homebrew source")
            sys.exit(1)

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


def run_export(args) -> None:
    """Export app list to JSON."""
    apps = load_apps()
    
    output = {
        "version": "0.2.0",
        "exported_at": datetime.now().isoformat(),
        "apps": [app.to_dict() for app in apps],
        "count": len(apps),
    }
    
    output_json = json.dumps(output, indent=2)
    
    if args.file:
        args.file.write_text(output_json, encoding="utf-8")
        print(f"Exported {len(apps)} apps to {args.file}")
    else:
        print(output_json)
    
    logger.info("Exported %d apps", len(apps))


def run_import(args) -> None:
    """Import apps from JSON file."""
    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)
    
    try:
        data = json.loads(args.file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    
    imported_apps = data.get("apps", [])
    if not imported_apps:
        print("No apps found in import file.")
        return
    
    if getattr(args, "merge", False):
        existing = load_apps()
        existing_ids = {app.id for app in existing}
        existing_winget = {app.winget_id for app in existing if app.winget_id}
        existing_github = {app.github_repo for app in existing if app.github_repo}
        existing_homebrew = {app.homebrew_formula for app in existing if app.homebrew_formula}
        
        added = 0
        skipped = 0
        
        for app_data in imported_apps:
            app_id = app_data.get("id", "")
            winget_id = app_data.get("winget_id")
            github_repo = app_data.get("github_repo")
            homebrew_formula = app_data.get("homebrew_formula")
            
            if app_id in existing_ids:
                skipped += 1
                continue
            if winget_id and winget_id in existing_winget:
                skipped += 1
                continue
            if github_repo and github_repo in existing_github:
                skipped += 1
                continue
            if homebrew_formula and homebrew_formula in existing_homebrew:
                skipped += 1
                continue
            
            app = App.from_dict(app_data)
            add_app(app)
            added += 1
        
        print(f"Imported {added} apps, skipped {skipped} duplicates.")
        logger.info("Imported %d apps (merged), skipped %d", added, skipped)
    else:
        apps = [App.from_dict(app_data) for app_data in imported_apps]
        save_apps(apps)
        print(f"Imported {len(apps)} apps (replaced existing).")
        logger.info("Imported %d apps (replaced)", len(apps))


if __name__ == "__main__":
    main()