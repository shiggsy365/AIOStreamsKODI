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
            parsed = urlparse(current_manifest)
            current_host = f'{parsed.scheme}://{parsed.netloc}'
            
            if current_host.lower() == host_url.lower():
                # Open with existing configuration
                use_manifest_config = True
        except:
            pass

    # Build configure URL
    if use_manifest_config:
        # Open with existing manifest URL to modify settings
        configure_url = current_manifest.replace('/manifest.json', '/configure')
    else:
        # Fresh configuration
        configure_url = f'{host_url}/stremio/configure'

    xbmc.log(f'[AIOStreams WebConfig] Opening configure page: {configure_url}', xbmc.LOGINFO)

    # Open browser
    if not open_browser(configure_url):
        xbmcgui.Dialog().ok(
            'AIOStreams Error',
            'Failed to open browser.\n'
            'Please open the following URL manually:\n\n'
            f'{configure_url}'
        )
        return None

    # Clear clipboard before monitoring
    clear_clipboard()
    xbmc.log('[AIOStreams WebConfig] Clipboard cleared, starting monitoring', xbmc.LOGDEBUG)

    # Show progress dialog with instructions
    progress = xbmcgui.DialogProgress()
    progress.create(
        'AIOStreams Configuration',
        'Configure AIOStreams in the browser that just opened.\n'
        'When finished, copy the manifest URL and it will be automatically detected.'
    )

    last_clipboard = ''
    timeout = 300  # 5 minutes
    start_time = time.time()
    poll_interval = 1  # Check every second
    manifest_url = None

    try:
        while not monitor.abortRequested():
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                progress.close()
                xbmcgui.Dialog().notification(
                    'AIOStreams',
                    'Configuration timed out',
                    xbmcgui.NOTIFICATION_WARNING
                )
                close_browser()
                return None

            # Update progress
            percent = int((elapsed / timeout) * 100)
            remaining = int(timeout - elapsed)
            progress.update(
                percent,
                f'Waiting for manifest URL... ({remaining}s remaining)\n'
                'Copy the manifest URL from the browser.'
            )

            # Check if user cancelled
            if progress.iscanceled():
                progress.close()
                xbmcgui.Dialog().notification(
                    'AIOStreams',
                    'Configuration cancelled',
                    xbmcgui.NOTIFICATION_WARNING
                )
                close_browser()
                return None

            # Get clipboard content
            clipboard_content = get_clipboard_content()

            if clipboard_content and clipboard_content != last_clipboard:
                last_clipboard = clipboard_content
                xbmc.log(f'[AIOStreams WebConfig] Clipboard changed, checking: {clipboard_content[:50]}...', xbmc.LOGDEBUG)

                # Check if it's a valid manifest URL
                if is_valid_manifest_url(clipboard_content):
                    manifest_url = clipboard_content.strip()

                    # Handle stremio:// protocol
                    if manifest_url.startswith('stremio://'):
                        manifest_url = 'https://' + manifest_url[10:]

                    xbmc.log(f'[AIOStreams WebConfig] Valid manifest URL detected: {manifest_url}', xbmc.LOGINFO)
                    break

            # Sleep before next poll
            monitor.waitForAbort(poll_interval)

    except KeyboardInterrupt:
        progress.close()
        return None

    # Close progress dialog
    progress.close()

    # If we got here without a manifest_url, user cancelled or timed out
    if not manifest_url:
        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Configuration cancelled',
            xbmcgui.NOTIFICATION_WARNING
        )
        close_browser()
        return None

    # Valid manifest URL detected - save it
    if manifest_url:
        addon.setSetting('base_url', manifest_url)

        # Try to extract and save the host URL
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
    3. Get 'encryptedPassword' from json response (at data.encryptedPassword)
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
        xbmc.log(f'[AIOStreams WebConfig] API response top-level keys: {list(data.keys())}', xbmc.LOGINFO)

        # FIXED: Navigate to data object (encryptedPassword is at data.encryptedPassword, NOT data.userData.encryptedPassword)
        response_data = data.get('data', {})
        
        if not response_data:
            progress.close()
            xbmcgui.Dialog().ok(
                'AIOStreams Error',
                'Could not retrieve data from server.\n'
                'Please check your UUID and password.'
            )
            xbmc.log('[AIOStreams WebConfig] No data in response', xbmc.LOGERROR)
            return None
        
        # Get encrypted password from data (NOT from userData)
        encrypted_password = response_data.get('encryptedPassword')
        if not encrypted_password:
            progress.close()
            xbmcgui.Dialog().ok(
                'AIOStreams Error',
                'Could not retrieve encrypted password from server.\n'
                'Please check your UUID and password.'
            )
            xbmc.log('[AIOStreams WebConfig] No encryptedPassword in data', xbmc.LOGERROR)
            return None

        # Get UUID from userData (use response UUID or fallback to input UUID)
        user_data = response_data.get('userData', {})
        uuid_from_response = user_data.get('uuid', uuid)

        progress.update(75, 'Building manifest URL...')

        # Construct manifest URL with encrypted password
        manifest_url = f'{host_url}/stremio/{uuid_from_response}/{encrypted_password}/manifest.json'
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
