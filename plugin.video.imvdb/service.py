import xbmc
import xbmcaddon
import xbmcgui
import json
import os
import requests
import xbmcvfs

ADDON = xbmcaddon.Addon('plugin.video.imvdb')
ADDON_ID = ADDON.getAddonInfo('id')

try:
    translatePath = xbmcvfs.translatePath
except AttributeError:
    translatePath = xbmc.translatePath

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] Service: {msg}", level)

def set_listitem_info(list_item, info):
    try:
        if hasattr(list_item, 'getVideoInfoTag'):
            tag = list_item.getVideoInfoTag()
            if 'title' in info: tag.setTitle(str(info['title']))
            if 'artist' in info: 
                tag.setArtists(info['artist'] if isinstance(info['artist'], list) else [str(info['artist'])])
            if 'year' in info: tag.setYear(int(info['year']))
            if 'mediatype' in info: tag.setMediaType(str(info['mediatype']))
        else:
            list_item.setInfo('video', info)
    except Exception as e:
        log(f"Error setting InfoTag: {str(e)}", xbmc.LOGDEBUG)
        list_item.setInfo('video', info)

class IMVDbPlayer(xbmc.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor = kwargs.get('monitor')

    def onPlayBackError(self):
        log("Playback Error detected! User requested automatic skip. Moving to next video...")
        # Small delay to allow Kodi to settle before skipping
        xbmc.sleep(1000)
        self.playnext()

class IMVDbMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.last_index = -1
        self.total_videos = 0
        self.is_active = False
        self.session_name = None
        self.loading = False
        self.last_trigger = ""

    def onNotification(self, sender, method, data):
        if sender == ADDON_ID and method == 'playlist_started':
            self.activate_loader(data)

    def activate_loader(self, session_name):
        log(f"Activating loader for session: {session_name}")
        xbmc.sleep(2000) # Wait for player
        self.session_name = session_name
        self.is_active = True
        self.last_index = -1
        self.loading = False
        self.load_total_count()

    def load_total_count(self):
        profile_path = translatePath(ADDON.getAddonInfo('profile'))
        list_file = os.path.join(profile_path, 'current_playlist.json')
        if os.path.exists(list_file):
            try:
                with open(list_file, 'r') as f:
                    self.total_videos = len(json.load(f))
            except:
                self.total_videos = 0
        log(f"Total videos in session list: {self.total_videos}")

    def get_youtube_id(self, video_id):
        api_key = ADDON.getSetting('api_key')
        headers = { 'IMVDB-APP-KEY': api_key, 'Accept': 'application/json' }
        url = f"https://imvdb.com/api/v1/video/{video_id}?include=sources"
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            for source in data.get('sources', []):
                if source.get('source') == 'youtube':
                    return source.get('source_data')
        except:
            pass
        return None

    def tick(self):
        # Check for Window Property fallback
        home_window = xbmcgui.Window(10000)
        current_trigger = home_window.getProperty('imvdb_trigger')
        if current_trigger and current_trigger != self.last_trigger:
            log("Detected new session via Window Property")
            self.last_trigger = current_trigger
            self.activate_loader(home_window.getProperty('imvdb_session'))

        if not self.is_active:
            return

        player = xbmc.Player()
        if not player.isPlayingVideo():
            return

        try:
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            current_index = playlist.getposition()
            playlist_size = playlist.size()

            if current_index != self.last_index:
                self.last_index = current_index
                
                # Buffer items: 5 items threshold, 10 items batch
                if not self.loading and current_index >= playlist_size - 5 and playlist_size > 0:
                    if playlist_size < self.total_videos:
                        self.load_next_batch(playlist_size)
                    else:
                        log("Reached end of available videos")
                        self.is_active = False
        except Exception as e:
            log(f"Tick error: {str(e)}", xbmc.LOGERROR)

    def load_next_batch(self, start_index):
        self.loading = True
        try:
            profile_path = translatePath(ADDON.getAddonInfo('profile'))
            list_file = os.path.join(profile_path, 'current_playlist.json')
            with open(list_file, 'r') as f:
                videos = json.load(f)

            log(f"Loading batch starting at {start_index}...")
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            
            resolved_any = False
            # Batch of 10
            for i in range(start_index, min(start_index + 10, len(videos))):
                v = videos[i]
                yt_id = self.get_youtube_id(v['id'])
                if yt_id:
                    plugin_url = f"plugin://plugin.video.youtube/play/?video_id={yt_id}"
                    list_item = xbmcgui.ListItem(label=v.get('song_title', ''))
                    list_item.setArt({'thumb': v.get('image', {}).get('l', '')})
                    set_listitem_info(list_item, {
                        'title': v.get('song_title'),
                        'artist': [a['name'] for a in v.get('artists', [])],
                        'year': int(v.get('year', 0)),
                        'mediatype': 'musicvideo'
                    })
                    playlist.add(url=plugin_url, listitem=list_item)
                    resolved_any = True
            
            if resolved_any:
                log(f"Batch success. New playlist size: {playlist.size()}")
        except Exception as e:
            log(f"Batch load error: {str(e)}", xbmc.LOGERROR)
        finally:
            self.loading = False

if __name__ == '__main__':
    log("Service Started")
    monitor = IMVDbMonitor()
    # Instantiate the custom player to handle auto-skip on error
    player = IMVDbPlayer(monitor=monitor)
    
    while not monitor.abortRequested():
        if monitor.waitForAbort(2):
            break
        monitor.tick()
    log("Service Stopped")
