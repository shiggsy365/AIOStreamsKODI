# -*- coding: utf-8 -*-
"""Playback monitoring for Trakt scrobbling"""
import xbmc
import xbmcaddon
from resources.lib import trakt

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
            return
        
        try:
            self.total_time = self.getTotalTime()
            self.current_time = self.getTime()
            
            # Scrobble start
            trakt.scrobble('start', self.media_type, self.imdb_id, 0, 
                          self.season, self.episode)
            self.started = True
            
            xbmc.log('[AIOStreams] Scrobble started', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Scrobble start error: {e}', xbmc.LOGERROR)
    
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
