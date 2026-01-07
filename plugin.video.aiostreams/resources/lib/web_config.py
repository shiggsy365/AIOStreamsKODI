# -*- coding: utf-8 -*-
"""
AIOStreams Web Configuration Module

Provides functionality to configure AIOStreams through a web browser.
Monitors clipboard for manifest URL after user configures in browser.
"""
import os
import sys
import platform
import webbrowser
import subprocess
import time

import xbmc
import xbmcgui
import xbmcaddon


def open_browser(url):
    """Open URL in the system browser, platform-aware."""
    system = platform.system().lower()

    xbmc.log(f'[AIOStreams WebConfig] Opening browser on {system}: {url}', xbmc.LOGINFO)

    # Check if running on Android
    if xbmc.getCondVisibility('System.Platform.Android'):
        # Use Android intent to open browser
        xbmc.executebuiltin(f'StartAndroidActivity("", "android.intent.action.VIEW", "", "{url}")')
        return True

    # For desktop platforms, use webbrowser module
    try:
        webbrowser.open(url, new=2)  # new=2 opens in new tab if possible
        return True
    except Exception as e:
        xbmc.log(f'[AIOStreams WebConfig] Failed to open browser: {e}', xbmc.LOGERROR)

        # Fallback: try system-specific commands
        try:
            if system == 'windows':
                os.startfile(url)
            elif system == 'darwin':
                os.system(f'open "{url}"')
            else:  # Linux
                os.system(f'xdg-open "{url}" &')
            return True
        except Exception as e2:
            xbmc.log(f'[AIOStreams WebConfig] Fallback browser open failed: {e2}', xbmc.LOGERROR)
            return False


def get_clipboard_content():
    """Try to get clipboard content (platform-specific)."""
    system = platform.system().lower()

    try:
        if system == 'windows':
            # Windows clipboard via PowerShell
            result = subprocess.run(
                ['powershell', '-command', 'Get-Clipboard'],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.returncode == 0:
                return result.stdout.strip()
        elif system == 'darwin':
            # macOS clipboard via pbpaste
            result = subprocess.run(
                ['pbpaste'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        else:
            # Linux - try xclip or xsel
            for cmd in [['xclip', '-selection', 'clipboard', '-o'], ['xsel', '--clipboard', '--output']]:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        return result.stdout.strip()
                except FileNotFoundError:
                    continue
    except Exception as e:
        xbmc.log(f'[AIOStreams WebConfig] Clipboard read failed: {e}', xbmc.LOGDEBUG)

    return None


def is_valid_manifest_url(text):
    """Check if text looks like a valid manifest URL."""
    if not text:
        return False
    text = text.strip()
    # Check for manifest.json in URL
    if 'manifest.json' in text.lower():
        # Should start with http or stremio://
        if text.startswith('http') or text.startswith('stremio://'):
            return True
    return False


def configure_aiostreams(host_url=None):
    """
    Main function to configure AIOStreams through web browser.

    Workflow:
    1. Open browser to configure page
    2. Monitor clipboard for manifest.json URL
    3. Auto-detect when user copies manifest URL
    4. Save to settings

    Args:
        host_url: Optional host URL. If not provided, uses current setting.

    Returns:
        str: The captured manifest URL, or None if cancelled/failed
    """
    addon = xbmcaddon.Addon()
    monitor = xbmc.Monitor()

    # Get or prompt for host URL
    if not host_url:
        host_url = addon.getSetting('aiostreams_host')

    if not host_url:
        # Prompt user for host URL
        host_url = xbmcgui.Dialog().input(
            'Enter AIOStreams Host URL',
            defaultt='https://aiostreams.elfhosted.com',
            type=xbmcgui.INPUT_ALPHANUM
        )
        if not host_url:
            return None
        addon.setSetting('aiostreams_host', host_url)

    # Clean up host URL
    host_url = host_url.rstrip('/')
    if host_url.endswith('/manifest.json'):
        host_url = host_url[:-14]
    if host_url.endswith('/configure'):
        host_url = host_url[:-10]

    # Check if we already have a manifest URL configured - use that for reconfiguration
    current_manifest = addon.getSetting('base_url')
    if current_manifest and current_manifest.strip():
        # Extract configure URL from manifest
        if '/manifest.json' in current_manifest:
            configure_url = current_manifest.replace('/manifest.json', '/configure')
        else:
            configure_url = current_manifest.rstrip('/') + '/configure'
    else:
        configure_url = host_url + '/stremio/configure'

    # Show instructions
    xbmcgui.Dialog().ok(
        'AIOStreams Configuration',
        'A browser will open to configure AIOStreams.\n\n'
        '1. Configure your settings in the browser\n'
        '2. Click [B]"Copy manifest to clipboard"[/B]\n'
        '3. The URL will be detected automatically'
    )

    # Clear any existing manifest URL from clipboard by reading current value
    initial_clipboard = get_clipboard_content()

    # Open browser
    if not open_browser(configure_url):
        # Offer to show URL manually
        if xbmcgui.Dialog().yesno(
            'Browser Failed',
            'Could not open browser automatically.\n\nWould you like to see the URL to open manually?'
        ):
            xbmcgui.Dialog().textviewer('Configuration URL', configure_url)

    # Monitor clipboard for manifest URL
    progress = xbmcgui.DialogProgress()
    progress.create(
        'Waiting for Configuration',
        'Configure AIOStreams in your browser...\n\n'
        'Click "Copy manifest to clipboard" when done.\n'
        'Press Cancel to enter URL manually.'
    )

    timeout = 300  # 5 minutes
    poll_interval = 1.0  # Check every second
    start_time = time.time()
    manifest_url = None

    while not monitor.abortRequested():
        elapsed = time.time() - start_time
        remaining = timeout - elapsed

        if remaining <= 0:
            break

        # Update progress
        percent = int((elapsed / timeout) * 100)
        mins, secs = divmod(int(remaining), 60)
        progress.update(
            percent,
            f'Waiting for manifest URL...\n\n'
            f'Copy manifest to clipboard in browser.\n'
            f'Time remaining: {mins}:{secs:02d}'
        )

        if progress.iscanceled():
            break

        # Check clipboard
        clipboard = get_clipboard_content()
        if clipboard and clipboard != initial_clipboard:
            if is_valid_manifest_url(clipboard):
                manifest_url = clipboard.strip()
                xbmc.log(f'[AIOStreams WebConfig] Detected manifest URL in clipboard', xbmc.LOGINFO)
                break

        # Wait before next poll
        if monitor.waitForAbort(poll_interval):
            break

    progress.close()

    # If we got a URL from clipboard
    if manifest_url:
        # Handle stremio:// URLs (convert to https://)
        if manifest_url.startswith('stremio://'):
            manifest_url = 'https://' + manifest_url[10:]
            xbmc.log(f'[AIOStreams WebConfig] Converted stremio:// URL to https://', xbmc.LOGDEBUG)

        # Save to settings
        addon.setSetting('base_url', manifest_url)

        # Also save/update the host URL for future use
        try:
            from urllib.parse import urlparse
            parsed = urlparse(manifest_url)
            host_base = f'{parsed.scheme}://{parsed.netloc}'
            addon.setSetting('aiostreams_host', host_base)
        except:
            pass

        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Configuration saved successfully!',
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

        xbmc.log(f'[AIOStreams WebConfig] Configuration saved: {manifest_url}', xbmc.LOGINFO)
        return manifest_url

    # No URL detected - offer manual entry
    if xbmcgui.Dialog().yesno(
        'No URL Detected',
        'Manifest URL was not detected.\n\n'
        'Would you like to paste it manually?'
    ):
        manifest_url = xbmcgui.Dialog().input(
            'Paste Manifest URL',
            type=xbmcgui.INPUT_ALPHANUM
        )

        if manifest_url:
            manifest_url = manifest_url.strip()

            # Handle stremio:// URLs
            if manifest_url.startswith('stremio://'):
                manifest_url = 'https://' + manifest_url[10:]

            # Validate
            if not manifest_url.startswith('http'):
                xbmcgui.Dialog().ok(
                    'Invalid URL',
                    'The URL should start with https://'
                )
                return None

            # Save
            addon.setSetting('base_url', manifest_url)

            try:
                from urllib.parse import urlparse
                parsed = urlparse(manifest_url)
                host_base = f'{parsed.scheme}://{parsed.netloc}'
                addon.setSetting('aiostreams_host', host_base)
            except:
                pass

            xbmcgui.Dialog().notification(
                'AIOStreams',
                'Configuration saved successfully!',
                xbmcgui.NOTIFICATION_INFO,
                3000
            )

            return manifest_url

    xbmcgui.Dialog().notification(
        'AIOStreams',
        'Configuration cancelled',
        xbmcgui.NOTIFICATION_WARNING
    )
    return None


def reconfigure_aiostreams():
    """
    Reconfigure existing AIOStreams setup.
    Opens the configure page for the current manifest URL.
    """
    addon = xbmcaddon.Addon()
    current_manifest = addon.getSetting('base_url')

    if current_manifest and current_manifest.strip():
        # Extract host from current manifest
        try:
            from urllib.parse import urlparse
            parsed = urlparse(current_manifest)
            host_url = f'{parsed.scheme}://{parsed.netloc}'
        except:
            host_url = None

        return configure_aiostreams(host_url)
    else:
        # No existing config, do fresh setup
        return configure_aiostreams()
