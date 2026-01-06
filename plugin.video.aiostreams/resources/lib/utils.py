# -*- coding: utf-8 -*-
"""
Utility functions for AIOStreams addon.
Includes smart widget refresh based on Seren's approach.
"""
import xbmc
import threading
import time


def wait_for_home_window(timeout=10):
    """Wait for Kodi home window to be active before proceeding.
    
    Based on Seren's approach to avoid refreshing widgets when user is not on home screen.
    This prevents UI flickering and ensures smooth user experience.
    
    Args:
        timeout: Maximum seconds to wait for home window (default: 10)
    
    Returns:
        bool: True if home window is active, False if timeout
    """
    start_time = time.time()
    monitor = xbmc.Monitor()
    
    while not monitor.abortRequested():
        # Check if we're on the home window (ID 10000)
        if xbmc.getCondVisibility('Window.IsActive(home)'):
            xbmc.log('[AIOStreams] Home window is active, ready for widget refresh', xbmc.LOGDEBUG)
            return True
        
        # Check timeout
        if time.time() - start_time > timeout:
            xbmc.log(f'[AIOStreams] Timeout waiting for home window after {timeout}s', xbmc.LOGDEBUG)
            return False
        
        # Wait a bit before checking again
        if monitor.waitForAbort(0.1):
            return False
    
    return False


def refresh_widgets():
    """Refresh Kodi widgets with smart timing.
    
    Waits for home window to be active before refreshing to avoid flickering.
    If not on home screen within timeout, refreshes anyway to ensure data consistency.
    """
    # Wait for home window (non-blocking approach)
    on_home = wait_for_home_window(timeout=5)
    
    if not on_home:
        xbmc.log('[AIOStreams] Not on home window, refreshing anyway', xbmc.LOGDEBUG)
    
    # Refresh widgets
    try:
        xbmc.executebuiltin('UpdateLibrary(video)')
        xbmc.log('[AIOStreams] Widgets refreshed successfully', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error refreshing widgets: {e}', xbmc.LOGERROR)


def refresh_container():
    """Refresh the current container/directory listing immediately."""
    try:
        xbmc.executebuiltin('Container.Refresh')
        xbmc.log('[AIOStreams] Container refreshed', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error refreshing container: {e}', xbmc.LOGERROR)


class BackgroundRefreshThread(threading.Thread):
    """Background thread for widget refresh after async operations.
    
    Allows UI to respond immediately while widgets update in background.
    """
    
    def __init__(self, delay=1.0):
        """Initialize background refresh thread.
        
        Args:
            delay: Seconds to wait before refreshing (default: 1.0)
        """
        super(BackgroundRefreshThread, self).__init__()
        self.delay = delay
        self.daemon = True  # Thread will not block app exit
    
    def run(self):
        """Run the background refresh after delay."""
        time.sleep(self.delay)
        refresh_widgets()


def trigger_background_refresh(delay=1.0):
    """Trigger widget refresh in background thread.
    
    Args:
        delay: Seconds to wait before refreshing (default: 1.0)
    """
    try:
        thread = BackgroundRefreshThread(delay=delay)
        thread.start()
        xbmc.log(f'[AIOStreams] Background refresh scheduled in {delay}s', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error starting background refresh: {e}', xbmc.LOGERROR)
        # Fallback to immediate refresh
        refresh_widgets()
