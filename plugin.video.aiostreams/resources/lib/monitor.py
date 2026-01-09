# -*- coding: utf-8 -*-
"""Playback monitoring for Trakt scrobbling and autoplay next episode"""
import xbmc
import xbmcaddon
from resources.lib import trakt
from resources.lib.autoplay import AutoplayManager

ADDON = xbmcaddon.Addon()


class AIOStreamsPlayer(xbmc.Player):
    """Custom player for monitoring playback and scrobbling to Trakt."""
    
    def __init__(self):
        xbmc.Player.__init__(self)
        self.is_aiostreams = False
        self.media_type = None
        self.imdb_id = None
        self.season = None
        self.episode = None
        self.started = False
        self.total_time = 0
        self.current_time = 0

        # Autoplay manager
        self.autoplay = AutoplayManager(self)
    
    def set_media_info(self, media_type, imdb_id, season=None, episode=None):
        """Set media information for scrobbling."""
        self.is_aiostreams = True
        self.media_type = media_type
        self.imdb_id = imdb_id
        self.season = season
        self.episode = episode
        self.started = False
        xbmc.log(f'[AIOStreams] Player set for {media_type}: {imdb_id}', xbmc.LOGINFO)
    
    def clear_media_info(self):
        """Clear media information."""
        self.is_aiostreams = False
        self.media_type = None
        self.imdb_id = None
        self.season = None
        self.episode = None
        self.started = False
        self.total_time = 0
        self.current_time = 0
    
    def should_scrobble(self):
        """Check if scrobbling is enabled and we have auth."""
        return (ADDON.getSetting('trakt_scrobble') == 'true' and 
                ADDON.getSetting('trakt_token') != '' and
                self.is_aiostreams and 
                self.imdb_id)
    
    def onPlayBackStarted(self):
        """Called when playback starts."""
        if not self.should_scrobble():
            # Check for autoplay even if not scrobbling
            self._check_autoplay_start()
            return

        try:
            self.total_time = self.getTotalTime()
            self.current_time = self.getTime()

            # Scrobble start
            trakt.scrobble('start', self.media_type, self.imdb_id, 0,
                          self.season, self.episode)
            self.started = True

            xbmc.log('[AIOStreams] Scrobble started', xbmc.LOGINFO)

            # Start autoplay monitoring if enabled
            self._check_autoplay_start()

        except Exception as e:
            xbmc.log(f'[AIOStreams] Scrobble start error: {e}', xbmc.LOGERROR)

    def _check_autoplay_start(self):
        """Check if autoplay should be started for this episode."""
        try:
            # Only autoplay for TV shows (not movies)
            if (self.is_aiostreams and
                self.media_type == 'series' and
                self.imdb_id and
                self.season is not None and
                self.episode is not None and
                self.autoplay.is_enabled()):

                xbmc.log(f'[AIOStreams] Starting autoplay for S{self.season:02d}E{self.episode:02d}',
                        xbmc.LOGINFO)
                self.autoplay.start_monitoring(self.imdb_id, self.season, self.episode)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking autoplay start: {e}', xbmc.LOGERROR)
    
    def onPlayBackPaused(self):
        """Called when playback is paused."""
        if not self.should_scrobble() or not self.started:
            return
        
        try:
            self.current_time = self.getTime()
            progress = int((self.current_time / self.total_time) * 100) if self.total_time > 0 else 0
            
            # Scrobble pause
            trakt.scrobble('pause', self.media_type, self.imdb_id, progress,
                          self.season, self.episode)
            
            xbmc.log(f'[AIOStreams] Scrobble paused at {progress}%', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Scrobble pause error: {e}', xbmc.LOGERROR)
    
    def onPlayBackResumed(self):
        """Called when playback resumes."""
        if not self.should_scrobble() or not self.started:
            return
        
        try:
            self.current_time = self.getTime()
            progress = int((self.current_time / self.total_time) * 100) if self.total_time > 0 else 0
            
            # Scrobble start again (resume)
            trakt.scrobble('start', self.media_type, self.imdb_id, progress,
                          self.season, self.episode)
            
            xbmc.log(f'[AIOStreams] Scrobble resumed at {progress}%', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Scrobble resume error: {e}', xbmc.LOGERROR)
    
    def onPlayBackStopped(self):
        """Called when playback stops."""
        # Stop autoplay monitoring
        try:
            self.autoplay.stop()
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error stopping autoplay: {e}', xbmc.LOGERROR)

        if not self.should_scrobble() or not self.started:
            self.clear_media_info()
            return

        try:
            progress = int((self.current_time / self.total_time) * 100) if self.total_time > 0 else 0

            # Scrobble stop
            trakt.scrobble('stop', self.media_type, self.imdb_id, progress,
                          self.season, self.episode)

            xbmc.log(f'[AIOStreams] Scrobble stopped at {progress}%', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Scrobble stop error: {e}', xbmc.LOGERROR)
        finally:
            self.clear_media_info()
    
    def onPlayBackEnded(self):
        """Called when playback ends."""
        # Stop autoplay monitoring (dialog may have handled this already)
        try:
            self.autoplay.stop()
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error stopping autoplay: {e}', xbmc.LOGERROR)

        if not self.should_scrobble() or not self.started:
            self.clear_media_info()
            return

        try:
            # Scrobble stop at 100%
            trakt.scrobble('stop', self.media_type, self.imdb_id, 100,
                          self.season, self.episode)

            xbmc.log('[AIOStreams] Scrobble completed at 100%', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Scrobble end error: {e}', xbmc.LOGERROR)
        finally:
            self.clear_media_info()
    
    def onPlayBackSeek(self, seekTime, seekOffset):
        """Called when user seeks."""
        if not self.should_scrobble() or not self.started:
            return
        
        try:
            self.current_time = self.getTime()
        except:
            pass


# Global player instance
PLAYER = AIOStreamsPlayer()
