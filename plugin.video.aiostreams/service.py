# -*- coding: utf-8 -*-
"""
AIOStreams background service for automatic Trakt sync and task processing.
Based on Seren's service patterns with background task queue support.
"""
import xbmc
import xbmcaddon
import time
import threading
import platform
from resources.lib.monitor import AIOStreamsPlayer


class BackgroundTaskQueue:
    """
    Thread-safe queue for background tasks.
    Allows deferring non-critical operations for background processing.
    """

    def __init__(self, max_size=100):
        """
        Initialize task queue.

        Args:
            max_size: Maximum number of pending tasks
        """
        self._queue = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._processing = False

    def add_task(self, func, *args, priority=0, description=None, **kwargs):
        """
        Add a task to the queue.

        Args:
            func: Function to execute
            *args: Positional arguments
            priority: Higher = processed first (default 0)
            description: Optional description for logging
            **kwargs: Keyword arguments
        """
        with self._lock:
            task = {
                'func': func,
                'args': args,
                'kwargs': kwargs,
                'priority': priority,
                'description': description or func.__name__,
                'added': time.time()
            }
            self._queue.append(task)
            xbmc.log(f'[AIOStreams Service] Task queued: {task["description"]}', xbmc.LOGDEBUG)

    def process_one(self):
        """
        Process one task from the queue.

        Returns:
            True if a task was processed, False if queue is empty
        """
        task = None

        with self._lock:
            if not self._queue:
                return False

            # Sort by priority (higher first) and get highest priority task
            sorted_tasks = sorted(self._queue, key=lambda t: t['priority'], reverse=True)
            task = sorted_tasks[0]
            self._queue.remove(task)

        if task:
            self._processing = True
            try:
                xbmc.log(f'[AIOStreams Service] Processing task: {task["description"]}', xbmc.LOGDEBUG)
                task['func'](*task['args'], **task['kwargs'])
                return True
            except Exception as e:
                xbmc.log(f'[AIOStreams Service] Task failed ({task["description"]}): {e}', xbmc.LOGERROR)
                return True  # Still return True since we processed it
            finally:
                self._processing = False

        return False

    def process_all(self, max_time=5.0):
        """
        Process tasks until queue is empty or max_time reached.

        Args:
            max_time: Maximum seconds to spend processing

        Returns:
            Number of tasks processed
        """
        start_time = time.time()
        processed = 0

        while time.time() - start_time < max_time:
            if self.process_one():
                processed += 1
            else:
                break

        return processed

    def clear(self):
        """Clear all pending tasks."""
        with self._lock:
            self._queue.clear()

    @property
    def pending_count(self):
        """Get number of pending tasks."""
        with self._lock:
            return len(self._queue)

    @property
    def is_processing(self):
        """Check if currently processing a task."""
        return self._processing


# Global task queue instance
_task_queue = None


def get_task_queue():
    """Get global BackgroundTaskQueue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = BackgroundTaskQueue()
    return _task_queue


def queue_task(func, *args, priority=0, description=None, **kwargs):
    """
    Queue a task for background processing.

    Args:
        func: Function to execute
        *args: Positional arguments
        priority: Higher = processed first
        description: Optional description
        **kwargs: Keyword arguments
    """
    get_task_queue().add_task(func, *args, priority=priority, description=description, **kwargs)


class AIOStreamsMonitor(xbmc.Monitor):
    """Monitor for Kodi events (settings changes, wake from sleep)."""

    def __init__(self, service):
        """
        Initialize monitor with reference to service.

        Args:
            service: Reference to AIOStreamsService instance
        """
        super().__init__()
        self.service = service
        self._is_sleeping = False

    def onSettingsChanged(self):
        """Called when addon settings are changed."""
        xbmc.log('[AIOStreams Service] Settings changed, reloading', xbmc.LOGINFO)
        self.service.reload_settings()

    def onScreensaverActivated(self):
        """Called when screensaver is activated (potential sleep)."""
        self._is_sleeping = True
        xbmc.log('[AIOStreams Service] Screensaver activated', xbmc.LOGDEBUG)

    def onScreensaverDeactivated(self):
        """Called when screensaver is deactivated (potential wake from sleep)."""
        was_sleeping = self._is_sleeping
        self._is_sleeping = False

        if was_sleeping:
            xbmc.log('[AIOStreams Service] Screensaver deactivated, triggering sync', xbmc.LOGINFO)
            self.service.sync_on_wake()

    @property
    def is_sleeping(self):
        """Check if system appears to be in sleep/screensaver state."""
        return self._is_sleeping


class AIOStreamsService:
    """Background service for automatic Trakt sync and task processing."""

    # Android sleep detection delay (seconds to wait for network)
    ANDROID_WAKE_DELAY = 5

    def __init__(self):
        """Initialize service."""
        self.addon = xbmcaddon.Addon()
        self.monitor = AIOStreamsMonitor(self)
        self.player = AIOStreamsPlayer()
        self.task_queue = get_task_queue()
        self.sync_interval = 5 * 60  # 5 minutes in seconds
        self.last_sync = 0
        self.auto_sync_enabled = True
        self._is_android = self._detect_android()
        self.reload_settings()
        xbmc.log('[AIOStreams Service] Service initialized', xbmc.LOGINFO)

    def _detect_android(self):
        """Detect if running on Android platform."""
        try:
            system = platform.system().lower()
            release = platform.release().lower()
            return system == 'linux' and 'android' in release
        except:
            return False

    def reload_settings(self):
        """Reload settings from addon."""
        try:
            # Reload addon reference to get fresh settings
            self.addon = xbmcaddon.Addon()
            self.auto_sync_enabled = self.addon.getSetting('trakt_sync_auto') == 'true'
            xbmc.log(f'[AIOStreams Service] Auto-sync enabled: {self.auto_sync_enabled}', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams Service] Error reloading settings: {e}', xbmc.LOGERROR)

    def should_sync(self):
        """
        Check if it's time to sync.

        Returns:
            bool: True if sync should be performed
        """
        if not self.auto_sync_enabled:
            return False

        # Check if Trakt is authorized
        trakt_token = self.addon.getSetting('trakt_token')
        if not trakt_token:
            return False

        # Check if enough time has passed since last sync
        current_time = time.time()
        if current_time - self.last_sync >= self.sync_interval:
            return True

        return False

    def perform_sync(self, force=False):
        """
        Perform Trakt sync.

        Args:
            force: If True, bypass throttle check
        """
        try:
            xbmc.log('[AIOStreams Service] Starting automatic Trakt sync', xbmc.LOGINFO)

            # Import here to avoid circular imports
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase

            db = TraktSyncDatabase()
            result = db.sync_activities(silent=True, force=force)

            if result is None:
                xbmc.log('[AIOStreams Service] Sync throttled (too soon since last sync)', xbmc.LOGDEBUG)
            elif result:
                xbmc.log('[AIOStreams Service] Sync completed successfully', xbmc.LOGINFO)
            else:
                xbmc.log('[AIOStreams Service] Sync completed with errors', xbmc.LOGWARNING)

            self.last_sync = time.time()

        except Exception as e:
            xbmc.log(f'[AIOStreams Service] Error during sync: {e}', xbmc.LOGERROR)

    def sync_on_wake(self):
        """Trigger sync when waking from sleep."""
        if not self.auto_sync_enabled:
            return

        # On Android, wait for network to come up
        if self._is_android:
            xbmc.log('[AIOStreams Service] Android detected, waiting for network...', xbmc.LOGINFO)
            self._wait_for_network()

        xbmc.log('[AIOStreams Service] Wake from sleep detected, syncing...', xbmc.LOGINFO)
        self.perform_sync(force=True)

    def _wait_for_network(self, max_wait=10):
        """
        Wait for network to become available (Android sleep recovery).

        Args:
            max_wait: Maximum seconds to wait
        """
        import requests

        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                # Quick connectivity check
                requests.head('https://api.trakt.tv', timeout=2)
                xbmc.log('[AIOStreams Service] Network available', xbmc.LOGDEBUG)
                return True
            except:
                time.sleep(1)

        xbmc.log('[AIOStreams Service] Network check timed out', xbmc.LOGWARNING)
        return False

    def run_migrations(self):
        """Run database migrations on startup."""
        try:
            from resources.lib.database.migration import DatabaseMigration
            migration = DatabaseMigration()
            if migration.is_migration_needed():
                xbmc.log('[AIOStreams Service] Running database migration...', xbmc.LOGINFO)
                results = migration.migrate()
                xbmc.log(f'[AIOStreams Service] Migration results: {results}', xbmc.LOGINFO)
            else:
                xbmc.log('[AIOStreams Service] No migration needed', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams Service] Migration check failed: {e}', xbmc.LOGERROR)

    def run_cache_cleanup(self):
        """Run cache cleanup on startup and periodically."""
        try:
            # 1. Cleanup file-based cache
            from resources.lib.cache import cleanup_expired_cache
            cleanup_expired_cache()
            
            # 2. Cleanup SQL-based cache
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
            db = TraktSyncDatabase()
            db.cleanup_cached_data()
            
            xbmc.log('[AIOStreams Service] Cache cleanup (File & SQL) completed', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams Service] Cache cleanup failed: {e}', xbmc.LOGERROR)

    def run(self):
        """Main service loop."""
        xbmc.log('[AIOStreams Service] Service started', xbmc.LOGINFO)

        # Run startup tasks
        self.run_migrations()
        self.run_cache_cleanup()

        # Main loop - check for sync every 30 seconds
        loop_count = 0
        while not self.monitor.abortRequested():
            # Check for sync
            if self.should_sync():
                self.perform_sync()

            # Process background tasks (up to 2 seconds per loop)
            processed = self.task_queue.process_all(max_time=2.0)
            if processed > 0:
                xbmc.log(f'[AIOStreams Service] Processed {processed} background tasks', xbmc.LOGDEBUG)

            # Periodic cache cleanup (every ~30 minutes)
            loop_count += 1
            if loop_count >= 60:  # 60 * 30 seconds = 30 minutes
                loop_count = 0
                queue_task(self.run_cache_cleanup, priority=-1, description='Periodic cache cleanup')

            # Wait for abort for 30 seconds (check more frequently for responsiveness)
            if self.monitor.waitForAbort(30):
                # Abort requested
                break

        xbmc.log('[AIOStreams Service] Service stopped', xbmc.LOGINFO)


if __name__ == '__main__':
    service = AIOStreamsService()
    service.run()
