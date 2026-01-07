# -*- coding: utf-8 -*-
"""
AIOStreams Web Configuration Module

Provides functionality to configure AIOStreams through a web browser
by running a local callback server to capture the stremio:// URL.
"""
import os
import sys
import socket
import threading
import time
import platform
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode

import xbmc
import xbmcgui
import xbmcaddon

# Callback server configuration
CALLBACK_PORT_START = 52420
CALLBACK_PORT_END = 52430
CALLBACK_TIMEOUT = 300  # 5 minutes timeout for user to complete configuration


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the callback server."""

    captured_url = None
    server_should_stop = False

    def log_message(self, format, *args):
        """Suppress default logging, use Kodi logging instead."""
        xbmc.log(f'[AIOStreams WebConfig] {format % args}', xbmc.LOGDEBUG)

    def do_GET(self):
        """Handle GET requests - capture the callback URL."""
        xbmc.log(f'[AIOStreams WebConfig] Received callback: {self.path}', xbmc.LOGINFO)

        # Parse the request path
        parsed = urlparse(self.path)

        if parsed.path == '/callback':
            # Get the stremio URL from query parameters
            params = parse_qs(parsed.query)
            stremio_url = params.get('url', [None])[0]

            if stremio_url:
                # Convert stremio:// to https://
                if stremio_url.startswith('stremio://'):
                    https_url = 'https://' + stremio_url[10:]
                else:
                    https_url = stremio_url

                CallbackHandler.captured_url = https_url
                xbmc.log(f'[AIOStreams WebConfig] Captured manifest URL: {https_url}', xbmc.LOGINFO)

                # Send success response with auto-close page
                self._send_success_response()
            else:
                self._send_error_response("No URL parameter received")

            # Signal server to stop
            CallbackHandler.server_should_stop = True

        elif parsed.path == '/status':
            # Status check endpoint
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "running"}')

        else:
            self.send_response(404)
            self.end_headers()

    def _send_success_response(self):
        """Send a success HTML page that auto-closes."""
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIOStreams - Configuration Saved</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            text-align: center;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 40px 60px;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .checkmark {
            font-size: 64px;
            margin-bottom: 20px;
        }
        h1 { margin: 0 0 10px 0; font-size: 28px; }
        p { margin: 0; opacity: 0.8; font-size: 16px; }
        .close-msg { margin-top: 20px; font-size: 14px; opacity: 0.6; }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✅</div>
        <h1>Configuration Saved!</h1>
        <p>Your AIOStreams manifest has been configured in Kodi.</p>
        <p class="close-msg">You can close this window and return to Kodi.</p>
    </div>
    <script>
        // Try to close the window after a delay
        setTimeout(function() {
            window.close();
        }, 3000);
    </script>
</body>
</html>'''

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html.encode('utf-8')))
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _send_error_response(self, error_msg):
        """Send an error HTML page."""
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AIOStreams - Error</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            text-align: center;
        }}
        .container {{
            background: rgba(255,0,0,0.1);
            padding: 40px 60px;
            border-radius: 16px;
        }}
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ margin: 0 0 10px 0; }}
        p {{ margin: 0; opacity: 0.8; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">❌</div>
        <h1>Configuration Error</h1>
        <p>{error_msg}</p>
    </div>
</body>
</html>'''

        self.send_response(400)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


class StoppableHTTPServer(HTTPServer):
    """HTTP Server that can be stopped from another thread."""

    allow_reuse_address = True

    def serve_until_stopped(self, timeout=CALLBACK_TIMEOUT):
        """Serve requests until stopped or timeout."""
        start_time = time.time()
        self.socket.settimeout(1.0)  # Check every second

        while not CallbackHandler.server_should_stop:
            try:
                self.handle_request()
            except socket.timeout:
                pass

            # Check timeout
            if time.time() - start_time > timeout:
                xbmc.log('[AIOStreams WebConfig] Callback server timed out', xbmc.LOGWARNING)
                break

            # Check if Kodi is shutting down
            if xbmc.Monitor().abortRequested():
                break


def find_available_port():
    """Find an available port for the callback server."""
    for port in range(CALLBACK_PORT_START, CALLBACK_PORT_END + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result != 0:  # Port is available
                return port
        except:
            pass
    return None


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


def configure_aiostreams(host_url=None):
    """
    Main function to configure AIOStreams through web browser.

    Args:
        host_url: Optional host URL. If not provided, uses current setting.

    Returns:
        str: The captured manifest URL, or None if cancelled/failed
    """
    addon = xbmcaddon.Addon()

    # Get or prompt for host URL
    if not host_url:
        host_url = addon.getSetting('aiostreams_host')

    if not host_url:
        # Prompt user for host URL
        keyboard = xbmcgui.Dialog().input(
            'Enter AIOStreams Host URL',
            defaultt='https://aiostreams.elfhosted.com',
            type=xbmcgui.INPUT_ALPHANUM
        )
        if not keyboard:
            return None
        host_url = keyboard
        addon.setSetting('aiostreams_host', host_url)

    # Clean up host URL
    host_url = host_url.rstrip('/')
    if host_url.endswith('/manifest.json'):
        host_url = host_url[:-14]
    if host_url.endswith('/configure'):
        host_url = host_url[:-10]

    # Check if we already have a manifest URL configured
    current_manifest = addon.getSetting('base_url')
    if current_manifest and current_manifest.strip():
        # Extract configure URL from manifest
        configure_url = current_manifest.replace('/manifest.json', '/configure')
        if not configure_url.endswith('/configure'):
            configure_url = host_url + '/stremio/configure'
    else:
        configure_url = host_url + '/stremio/configure'

    # Find available port for callback server
    port = find_available_port()
    if not port:
        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Could not find available port for callback',
            xbmcgui.NOTIFICATION_ERROR
        )
        return None

    # Reset handler state
    CallbackHandler.captured_url = None
    CallbackHandler.server_should_stop = False

    # Start callback server
    try:
        server = StoppableHTTPServer(('127.0.0.1', port), CallbackHandler)
        xbmc.log(f'[AIOStreams WebConfig] Started callback server on port {port}', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams WebConfig] Failed to start server: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Failed to start callback server',
            xbmcgui.NOTIFICATION_ERROR
        )
        return None

    # Build the configure URL with callback
    callback_url = f'http://127.0.0.1:{port}/callback'

    # Add callback parameter to configure URL
    if '?' in configure_url:
        full_url = f'{configure_url}&callback={callback_url}'
    else:
        full_url = f'{configure_url}?callback={callback_url}'

    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams Configuration', 'Opening browser for configuration...\n\nComplete the setup in your browser and click "Install to Stremio"')

    # Open browser
    if not open_browser(full_url):
        progress.close()
        server.server_close()

        # Offer to copy URL to clipboard instead
        if xbmcgui.Dialog().yesno(
            'Browser Failed',
            'Could not open browser automatically.\n\nWould you like to see the URL to open manually?'
        ):
            xbmcgui.Dialog().textviewer('Configuration URL', full_url)
        return None

    # Wait for callback in a thread
    server_thread = threading.Thread(target=server.serve_until_stopped, args=(CALLBACK_TIMEOUT,))
    server_thread.daemon = True
    server_thread.start()

    # Wait for completion with progress updates
    start_time = time.time()
    while server_thread.is_alive():
        elapsed = int(time.time() - start_time)
        remaining = CALLBACK_TIMEOUT - elapsed

        if remaining <= 0:
            break

        mins, secs = divmod(remaining, 60)
        progress.update(
            int((elapsed / CALLBACK_TIMEOUT) * 100),
            f'Waiting for configuration...\n\nComplete the setup in your browser.\nTime remaining: {mins}:{secs:02d}'
        )

        if progress.iscanceled():
            CallbackHandler.server_should_stop = True
            break

        time.sleep(0.5)

    progress.close()
    server.server_close()

    # Check result
    if CallbackHandler.captured_url:
        manifest_url = CallbackHandler.captured_url

        # Save to settings
        addon.setSetting('base_url', manifest_url)

        # Also save the host URL for future use
        parsed = urlparse(manifest_url)
        host_base = f'{parsed.scheme}://{parsed.netloc}'
        addon.setSetting('aiostreams_host', host_base)

        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Configuration saved successfully!',
            xbmcgui.NOTIFICATION_INFO,
            3000
        )

        xbmc.log(f'[AIOStreams WebConfig] Configuration saved: {manifest_url}', xbmc.LOGINFO)
        return manifest_url
    else:
        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Configuration cancelled or timed out',
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
        parsed = urlparse(current_manifest)
        host_url = f'{parsed.scheme}://{parsed.netloc}'

        # Get the configure URL (replace manifest.json with configure)
        if '/manifest.json' in current_manifest:
            configure_base = current_manifest.replace('/manifest.json', '')
        else:
            configure_base = current_manifest.rstrip('/')

        return configure_aiostreams(host_url)
    else:
        # No existing config, do fresh setup
        return configure_aiostreams()
