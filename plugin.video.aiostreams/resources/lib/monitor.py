# -*- coding: utf-8 -*-
"""Playback monitoring for Trakt scrobbling and autoplay next episode"""
import xbmc
import xbmcaddon
import xbmcgui
import threading
import time
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
        self.marked_watched = False
        self.progress_monitor_thread = None
        self.stop_monitoring = threading.Event()

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
        # Stop progress monitoring
        self._stop_progress_monitoring()

        self.is_aiostreams = False
        self.media_type = None
        self.imdb_id = None
        self.season = None
        self.episode = None
        self.started = False
        self.total_time = 0
        self.current_time = 0
        self.marked_watched = False
    
    def should_scrobble(self):
        """Check if scrobbling is enabled and we have auth."""
        return (ADDON.getSetting('trakt_scrobble') == 'true' and
                ADDON.getSetting('trakt_token') != '' and
                self.is_aiostreams and
                self.imdb_id)

    def should_auto_mark_watched(self):
        """Check if auto-mark watched is enabled."""
        return (ADDON.getSetting('trakt_auto_mark_watched') == 'true' and
                ADDON.getSetting('trakt_token') != '' and
                self.is_aiostreams and
                self.imdb_id and
                not self.marked_watched)

    def _monitor_progress(self):
        """Monitor playback progress and auto-mark as watched at 90%."""
        xbmc.log('[AIOStreams] Progress monitoring thread started', xbmc.LOGDEBUG)

        while not self.stop_monitoring.is_set():
            try:
                if not self.isPlaying():
                    break

                # Update current time
                self.current_time = self.getTime()
                if self.total_time == 0:
                    self.total_time = self.getTotalTime()

                # Calculate progress
                if self.total_time > 0:
                    progress = (self.current_time / self.total_time) * 100

                    # Auto-mark as watched at 90%+
                    if progress >= 90 and self.should_auto_mark_watched():
                        xbmc.log(f'[AIOStreams] Progress {progress:.1f}% - Auto-marking as watched', xbmc.LOGINFO)
                        self._auto_mark_watched()
                        break  # Stop monitoring after marking

            except Exception as e:
                xbmc.log(f'[AIOStreams] Progress monitor error: {e}', xbmc.LOGERROR)
                break

            # Check every 5 seconds
            if self.stop_monitoring.wait(5):
                break

        xbmc.log('[AIOStreams] Progress monitoring thread stopped', xbmc.LOGDEBUG)

    def _start_progress_monitoring(self):
        """Start the progress monitoring thread."""
        if self.progress_monitor_thread and self.progress_monitor_thread.is_alive():
            return  # Already monitoring

        self.stop_monitoring.clear()
        self.progress_monitor_thread = threading.Thread(target=self._monitor_progress)
        self.progress_monitor_thread.daemon = True
        self.progress_monitor_thread.start()
        xbmc.log('[AIOStreams] Progress monitoring started', xbmc.LOGINFO)

    def _stop_progress_monitoring(self):
        """Stop the progress monitoring thread."""
        self.stop_monitoring.set()
        if self.progress_monitor_thread and self.progress_monitor_thread.is_alive():
            self.progress_monitor_thread.join(timeout=1)
            xbmc.log('[AIOStreams] Progress monitoring stopped', xbmc.LOGINFO)

    def _auto_mark_watched(self):
        """Auto-mark content as watched and refresh widget."""
        try:
            self.marked_watched = True  # Set flag to prevent double-marking

            xbmc.log(f'[AIOStreams] Auto-marking as watched: {self.media_type} - {self.imdb_id}', xbmc.LOGINFO)

            # Mark as watched
            success = trakt.mark_watched(
                self.media_type,
                self.imdb_id,
                season=self.season,
                episode=self.episode
            )

            if success:
                xbmc.log('[AIOStreams] Successfully auto-marked as watched', xbmc.LOGINFO)

                # Refresh the container/widget
                self._refresh_widget()
            else:
                xbmc.log('[AIOStreams] Failed to auto-mark as watched', xbmc.LOGWARNING)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error auto-marking as watched: {e}', xbmc.LOGERROR)

    def _refresh_widget(self):
        """Refresh the current widget/container."""
        try:
            # Give Trakt a moment to sync
            time.sleep(0.5)

            # Refresh container
            xbmc.executebuiltin('Container.Refresh')
            xbmc.log('[AIOStreams] Widget refreshed', xbmc.LOGINFO)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error refreshing widget: {e}', xbmc.LOGERROR)

    def onPlayBackStarted(self):
        """Called when playback starts."""
        # Start progress monitoring for auto-mark watched (regardless of scrobbling)
        if self.is_aiostreams and self.should_auto_mark_watched():
            self._start_progress_monitoring()

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
            # Only autoplay for TV shows (series or episode media type)
            if (self.is_aiostreams and
                self.media_type in ('series', 'episode') and
                self.imdb_id and
                self.season is not None and
                self.episode is not None):

                # 1. Start internal AutoplayManager (for the dialog/background scraping)
                if self.autoplay.is_enabled():
                    xbmc.log(f'[AIOStreams] Starting autoplay monitoring for {self.media_type} S{self.season:02d}E{self.episode:02d}',
                            xbmc.LOGINFO)
                    self.autoplay.start_monitoring(self.imdb_id, self.season, self.episode)

                # 2. Integrate with UpNext script (service.upnext)
                self._signal_upnext()

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking autoplay start: {e}', xbmc.LOGERROR)

    def _signal_upnext(self):
        """Signal the UpNext script if available."""
        if xbmc.getCondVisibility('System.HasAddon(service.upnext)'):
            try:
                xbmc.log('[AIOStreams] Signaling UpNext script', xbmc.LOGINFO)
                
                # UpNext expect a JSON document with play details
                # We trigger it via a specific property or command depending on its version
                # Most common is setting a property or calling its service directly
                
                # Build the next episode data
                next_season = self.season
                next_episode = self.episode + 1
                
                # Fetch next episode info if possible
                from addon import get_meta
                next_meta = get_meta('series', f"{self.imdb_id}:{next_season}:{next_episode}")
                
                if next_meta:
                    meta = next_meta.get('meta', {})
                    upnext_data = {
                        'current_episode': {
                            'title': xbmc.getInfoLabel('ListItem.Title'),
                            'season': self.season,
                            'episode': self.episode,
                            'tvshowid': self.imdb_id
                        },
                        'next_episode': {
                            'title': meta.get('title', meta.get('name', 'Next Episode')),
                            'season': next_season,
                            'episode': next_episode,
                            'art': {
                                'thumb': meta.get('thumb', ''),
                                'poster': meta.get('poster', ''),
                                'fanart': meta.get('background', '')
                            }
                        },
                        'play_url': f'plugin://plugin.video.aiostreams/?action=play&content_type=series&imdb_id={self.imdb_id}&season={next_season}&episode={next_episode}'
                    }
                    
                    # Set the property for UpNext to find
                    window = xbmcgui.Window(10000)
                    window.setProperty('UpNext.Data', json.dumps(upnext_data))
                    
                    # Also trigger the specialized signal if needed
                    xbmc.executebuiltin(f'NotifyAll(service.upnext, {json.dumps(upnext_data)})')
            except Exception as e:
                xbmc.log(f'[AIOStreams] Error signaling UpNext: {e}', xbmc.LOGERROR)

    def onPlayBackEnded(self):
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

        # Check if we should auto-mark as watched before cleanup
        try:
            if self.is_aiostreams and self.total_time > 0:
                # Update current time before checking progress
                try:
                    self.current_time = self.getTime()
                except:
                    pass  # Use last known time if getTime() fails

                progress = int((self.current_time / self.total_time) * 100)
                if progress >= 90 and self.should_auto_mark_watched():
                    xbmc.log(f'[AIOStreams] Stopped at {progress}% - Auto-marking as watched', xbmc.LOGINFO)
                    self._auto_mark_watched()
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking auto-mark on stop: {e}', xbmc.LOGERROR)

        if not self.should_scrobble() or not self.started:
            self.clear_media_info()
            # Refresh widget after playback ends
            if self.marked_watched:
                self._refresh_widget()
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
            # Refresh widget after playback ends if marked watched
            if self.marked_watched:
                self._refresh_widget()
            self.clear_media_info()
    
    def onPlayBackEnded(self):
        """Called when playback ends."""
        # Stop autoplay monitoring (dialog may have handled this already)
        try:
            self.autoplay.stop()
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error stopping autoplay: {e}', xbmc.LOGERROR)

        # Auto-mark as watched if enabled (playback completed)
        try:
            if self.is_aiostreams and self.should_auto_mark_watched():
                xbmc.log('[AIOStreams] Playback ended - Auto-marking as watched', xbmc.LOGINFO)
                self._auto_mark_watched()
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error auto-marking on playback end: {e}', xbmc.LOGERROR)

        if not self.should_scrobble() or not self.started:
            self.clear_media_info()
            # Refresh widget after playback ends
            if self.marked_watched:
                self._refresh_widget()
            return

        try:
            # Scrobble stop at 100%
            trakt.scrobble('stop', self.media_type, self.imdb_id, 100,
                          self.season, self.episode)

            xbmc.log('[AIOStreams] Scrobble completed at 100%', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Scrobble end error: {e}', xbmc.LOGERROR)
        finally:
            # Refresh widget after playback ends if marked watched
            if self.marked_watched:
                self._refresh_widget()
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
