# -*- coding: utf-8 -*-
"""Playback monitoring for Trakt scrobbling and autoplay next episode"""
import xbmc
import xbmcaddon
import xbmcgui
import threading
import xbmc
import xbmcgui
import threading
import time
import json
import sys
import base64
from urllib.parse import quote_plus, parse_qsl, unquote_plus
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
        self.marked_watched = False
        self.progress_monitor_thread = None
        self.stop_monitoring = threading.Event()

        self.stop_monitoring = threading.Event()
    
    def set_media_info(self, media_type, imdb_id, season=None, episode=None):
        """Set media information for scrobbling."""
        self.is_aiostreams = True
        self.media_type = media_type
        self.imdb_id = imdb_id
        try:
            self.season = int(season) if season is not None else None
        except ValueError:
            self.season = season
            
        try:
            self.episode = int(episode) if episode is not None else None
        except ValueError:
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
                    # Auto-Skip Short Streams (e.g. trailers/wrong files < 95s)
                    # Helper prevents looping if the next stream is also short (we could add logic for that, but safe for now)
                    if self.total_time < 95 and self.total_time > 0 and self.current_time > 5 and not getattr(self, 'skipped_short_stream', False):
                        xbmc.log(f'[AIOStreams] Stream too short ({self.total_time}s < 95s) - Auto-skipping to next source', xbmc.LOGINFO)
                        self.skipped_short_stream = True
                        
                        # Stop current playback
                        # We use Player().stop() but we need to trigger the next action cleanly
                        # If we just run the plugin command, it might conflict if player is still running?
                        # UpNext uses Player().play(url) which internally stops current.
                        
                        # Trigger Play Next Source
                        # We use executebuiltin to run the plugin action asynchronously
                        url = 'plugin://plugin.video.aiostreams/?action=play_next_source'
                        xbmc.executebuiltin(f'RunPlugin({url})')
                        break

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
                self.episode is not None and
                ADDON.getSetting('autoplay_next_episode') == 'true'):

                # Integrate with UpNext script (service.upnext)
                self._signal_upnext()

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking autoplay start: {e}', xbmc.LOGERROR)

    def _signal_upnext(self):
        """Signal the UpNext script if available (async)."""
        if xbmc.getCondVisibility('System.HasAddon(service.upnext)'):
            threading.Thread(target=self._upnext_worker).start()

    def _upnext_worker(self):
        """Worker to wait for metadata/duration before signaling UpNext."""
        try:
            # Wait for valid duration and metadata
            # UpNext will stop tracking if it thinks the file isn't playing (duration 0)
            retries = 20
            while retries > 0:
                if not self.isPlaying():
                    return
                
                duration = self.getTotalTime()
                title = xbmc.getInfoLabel('ListItem.Title')
                
                if duration > 0 and title:
                    break
                    
                time.sleep(0.5)
                retries -= 1
            
            xbmc.log('[AIOStreams] Signaling UpNext script', xbmc.LOGINFO)
            
            from addon import get_meta
            
            # Build the next episode data
            next_season = self.season
            next_episode = self.episode + 1
            
            # Fetch next episode info if possible
            next_meta = get_meta('series', f"{self.imdb_id}:{next_season}:{next_episode}")
            
            if next_meta:
                meta = next_meta.get('meta', {})
                current_runtime = str(int(self.getTotalTime()))
                
                # Encode params to avoid URL issues
                from urllib.parse import urlencode
                play_params = {
                    'action': 'play',  # Use 'play' instead of 'play_next' - it's marked as IsPlayable
                    'content_type': 'series',
                    'imdb_id': self.imdb_id,
                    'season': str(next_season),
                    'episode': str(next_episode),
                    'force_autoplay': 'true'  # Flag to bypass show_streams dialog
                }
                play_url = f'plugin://plugin.video.aiostreams/?{urlencode(play_params)}'
                
                xbmc.log(f'[AIOStreams] UpNext play_url: {play_url}', xbmc.LOGINFO)
                
                # Store next episode params for our custom playback handler
                # We'll monitor for when service.upnext tries to play and intercept it
                window = xbmcgui.Window(10000)
                window.setProperty('AIOStreams.UpNext.IMDbID', self.imdb_id)
                window.setProperty('AIOStreams.UpNext.Season', str(next_season))
                window.setProperty('AIOStreams.UpNext.Episode', str(next_episode))
                
                # Signal service.upnext for the popup, but we'll handle playback ourselves
                upnext_data = {
                    'current_episode': {
                        'episodeid': str(self.episode),
                        'tvshowid': self.imdb_id,
                        'title': xbmc.getInfoLabel('ListItem.Title'),
                        'art': {
                            'thumb': xbmc.getInfoLabel('ListItem.Art(thumb)'),
                            'tvshow.poster': xbmc.getInfoLabel('ListItem.Art(tvshow.poster)'),
                            'tvshow.fanart': xbmc.getInfoLabel('ListItem.Art(tvshow.fanart)'),
                            'tvshow.clearart': xbmc.getInfoLabel('ListItem.Art(tvshow.clearart)'),
                            'tvshow.clearlogo': xbmc.getInfoLabel('ListItem.Art(tvshow.clearlogo)'),
                            'tvshow.landscape': xbmc.getInfoLabel('ListItem.Art(tvshow.landscape)')
                        },
                        'season': str(self.season),
                        'episode': str(self.episode),
                        'showtitle': xbmc.getInfoLabel('ListItem.TVShowTitle'),
                        'plot': xbmc.getInfoLabel('ListItem.Plot'),
                        'playcount': 0,
                        'rating': 0,
                        'firstaired': xbmc.getInfoLabel('ListItem.Premiered'),
                        'runtime': current_runtime
                    },
                    'next_episode': {
                        'episodeid': str(next_episode),
                        'tvshowid': self.imdb_id,
                        'title': meta.get('title', meta.get('name', 'Next Episode')),
                        'art': {
                            'thumb': meta.get('thumb', ''),
                            'tvshow.poster': meta.get('poster', ''),
                            'tvshow.fanart': meta.get('background', ''),
                            'tvshow.clearart': '',
                            'tvshow.clearlogo': '',
                            'tvshow.landscape': ''
                        },
                        'season': str(next_season),
                        'episode': str(next_episode),
                        'showtitle': xbmc.getInfoLabel('ListItem.TVShowTitle'),
                        'plot': meta.get('plot', meta.get('description', '')),
                        'playcount': 0,
                        'rating': 0,
                        'firstaired': meta.get('released', '').split('T')[0] if meta.get('released') else ''
                    },
                    'play_url': play_url,  # Provide URL for service.upnext popup
                    'notification_time': 30,
                    'notification_offset': 30,
                    'id': 'plugin.video.aiostreams_play_action'
                }
                
                # Set the property for UpNext to find
                window.setProperty('UpNext.Data', json.dumps(upnext_data))
                
                # Signal via JSON-RPC
                data_b64 = base64.b64encode(json.dumps(upnext_data).encode('utf-8')).decode('utf-8')
                rpc_request = json.dumps({
                    "jsonrpc": "2.0",
                    "method": "JSONRPC.NotifyAll",
                    "params": {
                        "sender": "plugin.video.aiostreams",
                        "message": "upnext_data",
                        "data": [data_b64]
                    },
                    "id": 1
                })
                
                xbmc.executeJSONRPC(rpc_request)
                xbmc.log('[AIOStreams] Signaled UpNext (custom playback mode)', xbmc.LOGINFO)
                self._send_upnext_signal('upnext_data', upnext_data)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error signaling UpNext: {e}', xbmc.LOGERROR)

    def _send_upnext_signal(self, signal, data):
        """Send a signal via JSON-RPC to service.upnext."""
        try:
            # Service.upnext expects the data to be a list containing a single base64 encoded JSON string
            # [ base64_encoded_json_string ]
            
            # 1. Dump data to JSON string
            json_str = json.dumps(data)
            
            # 2. Base64 encode the string
            b64_data = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
            
            # Construct the JSON-RPC payload
            payload = {
                'jsonrpc': '2.0',
                'method': 'JSONRPC.NotifyAll',
                'params': {
                    'sender': 'plugin.video.aiostreams',
                    'message': signal,
                    'data': [b64_data]  # Wrap base64 string in list
                },
                'id': 1
            }
            
            # Execute the JSON-RPC call
            json_command = json.dumps(payload)
            response = xbmc.executeJSONRPC(json_command)
            
            xbmc.log(f'[AIOStreams] Sent UpNext signal via JSONRPC. Response: {response}', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error sending JSONRPC signal: {e}', xbmc.LOGERROR)

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
        
        # Check if we have Up Next params stored (meaning service.upnext popup was shown)
        try:
            window = xbmcgui.Window(10000)
            imdb_id = window.getProperty('AIOStreams.UpNext.IMDbID')
            season = window.getProperty('AIOStreams.UpNext.Season')
            episode = window.getProperty('AIOStreams.UpNext.Episode')
            
            if imdb_id and season and episode:
                xbmc.log(f'[AIOStreams] Playback stopped - triggering Up Next: {imdb_id} S{season}E{episode}', xbmc.LOGINFO)
                
                # Clear the properties
                window.clearProperty('AIOStreams.UpNext.IMDbID')
                window.clearProperty('AIOStreams.UpNext.Season')
                window.clearProperty('AIOStreams.UpNext.Episode')
                
                # Trigger playback of next episode via RunPlugin
                from urllib.parse import urlencode
                play_params = {
                    'action': 'play',
                    'content_type': 'series',
                    'imdb_id': imdb_id,
                    'season': season,
                    'episode': episode,
                    'force_autoplay': 'true'
                }
                play_url = f'plugin://plugin.video.aiostreams/?{urlencode(play_params)}'
                
                # Use a small delay to ensure the player is fully stopped
                xbmc.sleep(500)
                xbmc.executebuiltin(f'RunPlugin({play_url})')
                xbmc.log(f'[AIOStreams] Executed RunPlugin for next episode', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in Up Next handler: {e}', xbmc.LOGERROR)

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
