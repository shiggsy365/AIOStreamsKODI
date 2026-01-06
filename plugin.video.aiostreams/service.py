# -*- coding: utf-8 -*-
"""
AIOStreams background service for automatic Trakt sync.
Runs in the background and syncs Trakt data every 5 minutes.
"""
import xbmc
import xbmcaddon
import time


class AIOStreamsMonitor(xbmc.Monitor):
    """Monitor for Kodi events (settings changes, wake from sleep)."""
    
    def __init__(self, service):
        """Initialize monitor with reference to service.
        
        Args:
            service: Reference to AIOStreamsService instance
        """
        super().__init__()
        self.service = service
    
    def onSettingsChanged(self):
        """Called when addon settings are changed."""
        xbmc.log('[AIOStreams Service] Settings changed, reloading', xbmc.LOGINFO)
        self.service.reload_settings()
    
    def onScreensaverDeactivated(self):
        """Called when screensaver is deactivated (potential wake from sleep)."""
        xbmc.log('[AIOStreams Service] Screensaver deactivated, triggering sync', xbmc.LOGINFO)
        self.service.sync_on_wake()


class AIOStreamsService:
    """Background service for automatic Trakt sync."""
    
    def __init__(self):
        """Initialize service."""
        self.addon = xbmcaddon.Addon()
        self.monitor = AIOStreamsMonitor(self)
        self.sync_interval = 5 * 60  # 5 minutes in seconds
        self.last_sync = 0
        self.auto_sync_enabled = True
        self.reload_settings()
        xbmc.log('[AIOStreams Service] Service initialized', xbmc.LOGINFO)
    
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
        """Check if it's time to sync.
        
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
    
    def perform_sync(self):
        """Perform Trakt sync."""
        try:
            xbmc.log('[AIOStreams Service] Starting automatic Trakt sync', xbmc.LOGINFO)
            
            # Import here to avoid circular imports
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
            
            db = TraktSyncDatabase()
            result = db.sync_activities(silent=True)
            
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
        
        xbmc.log('[AIOStreams Service] Wake from sleep detected, syncing...', xbmc.LOGINFO)
        self.perform_sync()
    
    def run(self):
        """Main service loop."""
        xbmc.log('[AIOStreams Service] Service started', xbmc.LOGINFO)
        
        # Run migration check on startup
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
        
        # Main loop - check for sync every 30 seconds
        while not self.monitor.abortRequested():
            if self.should_sync():
                self.perform_sync()
            
            # Wait for abort for 30 seconds (check more frequently for responsiveness)
            if self.monitor.waitForAbort(30):
                # Abort requested
                break
        
        xbmc.log('[AIOStreams Service] Service stopped', xbmc.LOGINFO)


if __name__ == '__main__':
    service = AIOStreamsService()
    service.run()
