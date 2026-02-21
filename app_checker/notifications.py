"""Cross-platform desktop notifications."""

import platform
import subprocess
import sys
from typing import Optional

from .logging_config import get_logger

logger = get_logger(__name__)


def is_notification_supported() -> bool:
    """Check if notifications are supported on this platform."""
    system = platform.system()
    
    if system == "Windows":
        return True
    elif system == "Darwin":  # macOS
        return True
    elif system == "Linux":
        return bool(subprocess.run(["which", "notify-send"], capture_output=True).returncode == 0)
    
    return False


def send_notification(title: str, message: str) -> bool:
    """Send a desktop notification.
    
    Args:
        title: Notification title.
        message: Notification body.
        
    Returns:
        True if notification was sent successfully, False otherwise.
    """
    system = platform.system()
    
    try:
        if system == "Windows":
            return _notify_windows(title, message)
        elif system == "Darwin":
            return _notify_macos(title, message)
        elif system == "Linux":
            return _notify_linux(title, message)
        else:
            logger.warning("Notifications not supported on %s", system)
            return False
    except Exception as e:
        logger.error("Failed to send notification: %s", e)
        return False


def _notify_windows(title: str, message: str) -> bool:
    """Send notification on Windows."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="App Update Checker",
            timeout=10,
        )
        return True
    except ImportError:
        try:
            import win11toast
            win11toast.toast(title, message)
            return True
        except ImportError:
            logger.warning("plyer or win11toast not installed, falling back to balloon tip")
            return _notify_windows_fallback(title, message)
    except Exception as e:
        logger.error("Windows notification failed: %s", e)
        return False


def _notify_windows_fallback(title: str, message: str) -> bool:
    """Fallback Windows notification using PowerShell."""
    try:
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        
        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@
        
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("App Update Checker").Show($toast)
        '''
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)
        return True
    except Exception as e:
        logger.error("Windows fallback notification failed: %s", e)
        return False


def _notify_macos(title: str, message: str) -> bool:
    """Send notification on macOS."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception as e:
        logger.error("macOS notification failed: %s", e)
        return False


def _notify_linux(title: str, message: str) -> bool:
    """Send notification on Linux using notify-send."""
    try:
        subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception as e:
        logger.error("Linux notification failed: %s", e)
        return False


def notify_updates_available(count: int, app_names: Optional[list[str]] = None) -> bool:
    """Send notification about available updates.
    
    Args:
        count: Number of updates available.
        app_names: Optional list of app names with updates.
        
    Returns:
        True if notification was sent successfully.
    """
    title = f"{count} Update{'s' if count != 1 else ''} Available"
    
    if app_names and len(app_names) <= 5:
        message = ", ".join(app_names)
    elif app_names:
        message = f"{', '.join(app_names[:5])} and {len(app_names) - 5} more"
    else:
        message = f"{count} application{'s' if count != 1 else ''} have updates available."
    
    return send_notification(title, message)


def notify_all_up_to_date() -> bool:
    """Send notification that all apps are up to date."""
    return send_notification("All Apps Up to Date", "No updates available.")