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


def is_android():
    """Check if running on Android."""
    return xbmc.getCondVisibility('System.Platform.Android')


def close_browser():
    """Try to close the browser after configuration is complete."""
    system = platform.system().lower()

    try:
        if system == 'windows':
            # Close common browsers on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            for browser in ['chrome.exe', 'msedge.exe', 'firefox.exe', 'opera.exe', 'brave.exe']:
                try:
                    subprocess.run(
                        ['taskkill', '/IM', browser, '/F'],
                        capture_output=True,
                        timeout=3,
                        startupinfo=startupinfo
                    )
                except:
                    pass
            xbmc.log('[AIOStreams WebConfig] Attempted to close browser', xbmc.LOGDEBUG)

        elif system == 'darwin':
            # Close common browsers on macOS
            for browser in ['Google Chrome', 'Safari', 'Firefox', 'Microsoft Edge']:
                try:
                    subprocess.run(['pkill', '-f', browser], capture_output=True, timeout=3)
                except:
                    pass

        elif is_android():
            # On Android, try to go back to Kodi
            xbmc.executebuiltin('ActivateWindow(home)')

        else:
            # Linux - try pkill for common browsers
            for browser in ['chrome', 'chromium', 'firefox', 'opera', 'brave']:
                try:
                    subprocess.run(['pkill', '-f', browser], capture_output=True, timeout=3)
                except:
                    pass
    except Exception as e:
        xbmc.log(f'[AIOStreams WebConfig] Failed to close browser: {e}', xbmc.LOGDEBUG)


def clear_clipboard():
    """Clear the system clipboard (platform-specific)."""
    # Skip on Android - clipboard clearing doesn't work reliably
    if is_android():
        return

    system = platform.system().lower()

    try:
        if system == 'windows':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            subprocess.run(
                ['powershell', '-NoProfile', '-Command', 'Set-Clipboard -Value $null'],
                capture_output=True,
                timeout=3,
                startupinfo=startupinfo
            )
            xbmc.log('[AIOStreams WebConfig] Clipboard cleared', xbmc.LOGDEBUG)
        elif system == 'darwin':
            subprocess.run(['pbcopy'], input=b'', timeout=3)
        else:
            # Linux - try xclip or xsel
            for cmd in [['xclip', '-selection', 'clipboard'], ['xsel', '--clipboard', '--input']]:
                try:
                    subprocess.run(cmd, input=b'', timeout=3)
                    break
                except FileNotFoundError:
                    continue
    except Exception as e:
        xbmc.log(f'[AIOStreams WebConfig] Failed to clear clipboard: {e}', xbmc.LOGDEBUG)


def get_clipboard_content():
    """Try to get clipboard content (platform-specific)."""
    system = platform.system().lower()

    try:
        if system == 'windows':
            # Windows clipboard via PowerShell - use startupinfo to hide window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', 'Get-Clipboard'],
                capture_output=True,
                text=True,
                timeout=3,
                startupinfo=startupinfo
            )
            if result.returncode == 0:
                content = result.stdout.strip()
                return content
            else:
                xbmc.log(f'[AIOStreams WebConfig] PowerShell error: {result.stderr}', xbmc.LOGDEBUG)

        elif system == 'darwin':
            # macOS clipboard via pbpaste
            result = subprocess.run(
                ['pbpaste'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                return result.stdout.strip()
        else:
            # Linux - try xclip or xsel
            for cmd in [['xclip', '-selection', 'clipboard', '-o'], ['xsel', '--clipboard', '--output']]:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    if result.returncode == 0:
                        return result.stdout.strip()
                except FileNotFoundError:
                    continue
    except subprocess.TimeoutExpired:
        xbmc.log('[AIOStreams WebConfig] Clipboard read timed out', xbmc.LOGDEBUG)
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

    # Check if we already have a manifest URL configured
    current_manifest = addon.getSetting('base_url')
    use_manifest_config = False
    
    if current_manifest and current_manifest.strip():
        # Check if the host matches our current setting
        try:
            from urllib.parse import urlparse
            manifest_parsed = urlparse(current_manifest)
            manifest_host = f'{manifest_parsed.scheme}://{manifest_parsed.netloc}'
            
            # If hosts match (or close enough), use the manifest's configure URL (preserves state)
            # If they differ, the user likely changed the setting to switch hosts, so use the new host
            if host_url and manifest_host in host_url:
                use_manifest_config = True
            elif not host_url:
                use_manifest_config = True
        except:
            pass

    if use_manifest_config:
        # Extract configure URL from manifest
        if '/manifest.json' in current_manifest:
            configure_url = current_manifest.replace('/manifest.json', '/configure')
        else:
            configure_url = current_manifest.rstrip('/') + '/configure'
    else:
        # Use simple configure URL from the host setting
        configure_url = host_url + '/stremio/configure'

    # Check if on Android - use different flow (manual paste)
    on_android = is_android()

    if on_android:
        # Android: Show instructions for manual paste
        xbmcgui.Dialog().ok(
            'AIOStreams Configuration',
            'A browser will open to configure AIOStreams.\n\n'
            '1. Configure your settings in the browser\n'
            '2. Click [B]"Copy manifest to clipboard"[/B]\n'
            '3. Return to Kodi and paste the URL when prompted'
        )
    else:
        # Desktop: Show instructions for auto-detection
        xbmcgui.Dialog().ok(
            'AIOStreams Configuration',
            'A browser will open to configure AIOStreams.\n\n'
            '1. Configure your settings in the browser\n'
            '2. Click [B]"Copy manifest to clipboard"[/B]\n'
            '3. The URL will be detected automatically'
        )

        # Clear clipboard before starting to ensure clean detection
        clear_clipboard()
        xbmc.log('[AIOStreams WebConfig] Cleared clipboard before browser open', xbmc.LOGDEBUG)

    # Open browser
    browser_opened = open_browser(configure_url)
    if not browser_opened:
        # Offer to show URL manually
        if xbmcgui.Dialog().yesno(
            'Browser Failed',
            'Could not open browser automatically.\n\nWould you like to see the URL to open manually?'
        ):
            xbmcgui.Dialog().textviewer('Configuration URL', configure_url)

    # Give browser time to open before starting to monitor
    xbmc.sleep(2000)

    # Android: Skip clipboard monitoring, go straight to manual entry
    if on_android:
        manifest_url = xbmcgui.Dialog().input(
            'Paste Manifest URL',
            type=xbmcgui.INPUT_ALPHANUM
        )

        if manifest_url:
            manifest_url = manifest_url.strip()

            # Handle stremio:// URLs
            if manifest_url.startswith('stremio://'):
                manifest_url = 'https://' + manifest_url[10:]

            if is_valid_manifest_url(manifest_url) or manifest_url.startswith('http'):
                # Save to settings
                addon.setSetting('base_url', manifest_url)

                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(manifest_url)
                    host_base = f'{parsed.scheme}://{parsed.netloc}'
                    addon.setSetting('aiostreams_host', host_base)
                except:
                    pass

                # Try to return to Kodi
                close_browser()

                xbmcgui.Dialog().notification(
                    'AIOStreams',
                    'Configuration saved successfully!',
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                return manifest_url
            else:
                xbmcgui.Dialog().ok('Invalid URL', 'The URL should contain manifest.json or start with https://')

        xbmcgui.Dialog().notification('AIOStreams', 'Configuration cancelled', xbmcgui.NOTIFICATION_WARNING)
        return None

    # Monitor clipboard for manifest URL
    progress = xbmcgui.DialogProgress()
    progress.create(
        'Waiting for Configuration',
        'Configure AIOStreams in your browser...\n\n'
        'Click "Copy manifest to clipboard" when done.\n'
        'Press Cancel to enter URL manually.'
    )

    timeout = 300  # 5 minutes
    poll_interval = 1.5  # Check every 1.5 seconds
    start_time = time.time()
    manifest_url = None
    check_count = 0

    xbmc.log('[AIOStreams WebConfig] Starting clipboard monitoring loop', xbmc.LOGINFO)

    while True:
        # Check for abort
        if monitor.abortRequested():
            xbmc.log('[AIOStreams WebConfig] Abort requested', xbmc.LOGDEBUG)
            break

        elapsed = time.time() - start_time
        remaining = timeout - elapsed

        if remaining <= 0:
            xbmc.log('[AIOStreams WebConfig] Timeout reached', xbmc.LOGINFO)
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
            xbmc.log('[AIOStreams WebConfig] User cancelled', xbmc.LOGINFO)
            break

        # Check clipboard
        check_count += 1
        clipboard = get_clipboard_content()

        if check_count % 10 == 0:  # Log every 10 checks
            xbmc.log(f'[AIOStreams WebConfig] Clipboard check #{check_count}, content: {clipboard[:50] if clipboard else "None"}...', xbmc.LOGDEBUG)

        # Since we cleared the clipboard, any valid manifest URL is new
        if clipboard and is_valid_manifest_url(clipboard):
            manifest_url = clipboard.strip()
            xbmc.log(f'[AIOStreams WebConfig] Detected manifest URL: {manifest_url[:50]}...', xbmc.LOGINFO)
            break

        # Wait before next poll using Kodi's sleep (non-blocking)
        xbmc.sleep(int(poll_interval * 1000))

    progress.close()

    # If we got a URL from clipboard
    if manifest_url:
        # Handle stremio:// URLs (convert to https://)
        if manifest_url.startswith('stremio://'):
            manifest_url = 'https://' + manifest_url[10:]
            xbmc.log('[AIOStreams WebConfig] Converted stremio:// URL to https://', xbmc.LOGDEBUG)

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

        # Clear clipboard after saving for security
        clear_clipboard()
        xbmc.log('[AIOStreams WebConfig] Cleared clipboard after saving', xbmc.LOGDEBUG)

        # Close browser after successful configuration
        close_browser()

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


def retrieve_manifest():
    """
    Retrieve manifest URL using UUID and password authentication.

    Workflow:
    1. Get host URL, UUID, and password from settings
    2. Call [host url]/api/v1/user?uuid=[uuid]&password=[password]
    3. Get 'encryptedPassword' from json response
    4. Construct manifest URL as [host url]/stremio/[uuid]/[encryptedPassword]/manifest.json
    5. Save to base_url setting
    """
    import requests

    addon = xbmcaddon.Addon()

    # Get settings
    host_url = addon.getSetting('aiostreams_host')
    uuid = addon.getSetting('aiostreams_uuid')
    password = addon.getSetting('aiostreams_password')

    # Validate inputs
    if not host_url:
        xbmcgui.Dialog().ok(
            'AIOStreams',
            'Please enter the Host Base URL first.'
        )
        return None

    if not uuid:
        xbmcgui.Dialog().ok(
            'AIOStreams',
            'Please enter your UUID first.'
        )
        return None

    if not password:
        xbmcgui.Dialog().ok(
            'AIOStreams',
            'Please enter your Password first.'
        )
        return None

    # Clean up host URL
    host_url = host_url.rstrip('/')

    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Retrieving manifest...')

    try:
        # Build API URL
        api_url = f'{host_url}/api/v1/user?uuid={uuid}&password={password}'
        xbmc.log(f'[AIOStreams WebConfig] Calling API: {host_url}/api/v1/user?uuid={uuid}&password=***', xbmc.LOGINFO)

        progress.update(25, 'Contacting AIOStreams server...')

        # Make API request
        response = requests.get(api_url, timeout=15)

        progress.update(50, 'Processing response...')

        if response.status_code != 200:
            progress.close()
            error_msg = f'Server returned error: {response.status_code}'
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg = error_data['error']
                elif 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
            xbmcgui.Dialog().ok('AIOStreams Error', error_msg)
            xbmc.log(f'[AIOStreams WebConfig] API error: {error_msg}', xbmc.LOGERROR)
            return None

        # Parse response
        data = response.json()
        xbmc.log(f'[AIOStreams WebConfig] API response keys: {list(data.keys())}', xbmc.LOGDEBUG)

        # Get encrypted password
        encrypted_password = data.get('encryptedPassword')
        if not encrypted_password:
            progress.close()
            xbmcgui.Dialog().ok(
                'AIOStreams Error',
                'Could not retrieve encrypted password from server.\n'
                'Please check your UUID and password.'
            )
            xbmc.log('[AIOStreams WebConfig] No encryptedPassword in response', xbmc.LOGERROR)
            return None

        progress.update(75, 'Building manifest URL...')

        # Construct manifest URL
        manifest_url = f'{host_url}/stremio/{uuid}/{encrypted_password}/manifest.json'
        xbmc.log(f'[AIOStreams WebConfig] Constructed manifest URL: {manifest_url[:50]}...', xbmc.LOGINFO)

        # Save to settings
        addon.setSetting('base_url', manifest_url)

        progress.update(100, 'Configuration saved!')
        xbmc.sleep(500)
        progress.close()

        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Manifest URL retrieved successfully!',
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

        xbmc.log(f'[AIOStreams WebConfig] Manifest URL saved successfully', xbmc.LOGINFO)
        return manifest_url

    except requests.exceptions.Timeout:
        progress.close()
        xbmcgui.Dialog().ok(
            'AIOStreams Error',
            'Request timed out.\n'
            'Please check your internet connection and host URL.'
        )
        xbmc.log('[AIOStreams WebConfig] API request timed out', xbmc.LOGERROR)
        return None

    except requests.exceptions.ConnectionError as e:
        progress.close()
        xbmcgui.Dialog().ok(
            'AIOStreams Error',
            'Could not connect to server.\n'
            'Please check the host URL is correct.'
        )
        xbmc.log(f'[AIOStreams WebConfig] Connection error: {e}', xbmc.LOGERROR)
        return None

    except Exception as e:
        progress.close()
        xbmcgui.Dialog().ok(
            'AIOStreams Error',
            f'An error occurred:\n{str(e)}'
        )
        xbmc.log(f'[AIOStreams WebConfig] Unexpected error: {e}', xbmc.LOGERROR)
        return None
