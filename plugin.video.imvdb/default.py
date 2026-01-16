import sys
import os
import json
import random
import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
from urllib.parse import urlencode, parse_qsl

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1

try:
    translatePath = xbmcvfs.translatePath
except AttributeError:
    translatePath = xbmc.translatePath

COUNTRIES = [
    ('us', 'United States'), ('gb', 'United Kingdom'), ('ca', 'Canada'), ('au', 'Australia'),
    ('de', 'Germany'), ('fr', 'France'), ('jp', 'Japan'), ('kr', 'South Korea'),
    ('is', 'Iceland'), ('se', 'Sweden'), ('ar', 'Argentina'), ('it', 'Italy'),
    ('at', 'Austria'), ('mx', 'Mexico'), ('be', 'Belgium'), ('nl', 'Netherlands'),
    ('br', 'Brazil'), ('no', 'Norway'), ('ch', 'Switzerland'), ('nz', 'New Zealand'),
    ('dk', 'Denmark'), ('pl', 'Poland'), ('es', 'Spain'), ('ru', 'Russia'),
    ('fi', 'Finland'), ('za', 'South Africa')
]

def is_blocked(video):
    country = video.get('country')
    if not country: return False
    
    code = country.lower()
    setting_id = f'block_{code}'
    
    # Check if we have a setting for this country
    try:
        return ADDON.getSettingBool(setting_id)
    except:
        # Fallback if setting not found (though they should all be in settings.xml)
        return False

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] {msg}", level)

def build_url(query):
    return sys.argv[0] + '?' + urlencode(query)

def close_all_dialogs():
    """Aggressively close any existing dialogs to prevent 'concurrent busydialogs' crash."""
    xbmc.executebuiltin('Dialog.Close(all, true)')
    xbmc.sleep(200)

def show_busy():
    """Show the busy spinner as requested by the user, but safely."""
    close_all_dialogs()
    xbmc.executebuiltin('ActivateWindow(busydialog)')

def hide_busy():
    """Hide the busy spinner."""
    xbmc.executebuiltin('Dialog.Close(busydialog)')

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

def list_menu():
    xbmcplugin.setContent(HANDLE, 'files')
    items = [
        ('Artist Search', 'search_artist', 'DefaultArtist.png'),
        ('Year Search', 'search_year', 'DefaultYear.png')
    ]
    for label, action, icon in items:
        list_item = xbmcgui.ListItem(label=label)
        list_item.setArt({'icon': icon, 'thumb': icon})
        list_item.setProperty('IsPlayable', 'false')
        set_listitem_info(list_item, {'title': label, 'mediatype': 'video'})
        url = build_url({'action': action})
        # Use isFolder=True for root items to ensure widget visibility
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True)

def search_year():
    keyboard = xbmcgui.Dialog()
    year = keyboard.input('IMVDb Year Search', type=xbmcgui.INPUT_NUMERIC)
    if not year:
        return
    select_year(year)

def search_artist():
    keyboard = xbmcgui.Dialog()
    query = keyboard.input('IMVDb Artist Search', type=xbmcgui.INPUT_ALPHANUM)
    if not query:
        return
    
    show_busy()
    api_key = ADDON.getSetting('api_key')
    headers = {'IMVDB-APP-KEY': api_key, 'Accept': 'application/json'}
    url = f"https://imvdb.com/api/v1/search/videos?q={query}&per_page=50"
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        
        lower_query = query.lower()
        filtered_videos = []
        for v in results:
            if is_blocked(v): continue
            artists = v.get('artists', [])
            if any(artist and isinstance(artist.get('name'), str) and lower_query in artist.get('name').lower() for artist in artists):
                filtered_videos.append(v)
        
        if not filtered_videos:
            hide_busy()
            xbmcgui.Dialog().ok("IMVDb", f"No videos found for artist '{query}'")
            return

        play_videos(filtered_videos, query)
        
    except Exception as e:
        log(f"Error searching artists: {str(e)}", xbmc.LOGERROR)
        hide_busy()
        xbmcgui.Dialog().ok("IMVDb", f"Error: {str(e)}")

def fetch_videos_for_year(year):
    api_key = ADDON.getSetting('api_key')
    headers = {'IMVDB-APP-KEY': api_key, 'Accept': 'application/json'}
    url = f"https://imvdb.com/api/v1/search/videos?q={year}&per_page=250"
    try:
        response = requests.get(url, headers=headers, timeout=7)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        videos = [v for v in results if str(v.get('year')) == str(year) and not is_blocked(v)]
        return videos
    except Exception as e:
        log(f"Error fetching year videos: {str(e)}", xbmc.LOGERROR)
        return []

def get_youtube_id(video_id):
    api_key = ADDON.getSetting('api_key')
    headers = {'IMVDB-APP-KEY': api_key, 'Accept': 'application/json'}
    url = f"https://imvdb.com/api/v1/video/{video_id}?include=sources"
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        sources = data.get('sources', [])
        for source in sources:
            if source.get('source') == 'youtube':
                return source.get('source_data')
    except:
        pass
    return None

def select_year(year):
    show_busy()
    videos = fetch_videos_for_year(year)
    if not videos:
        hide_busy()
        xbmcgui.Dialog().ok("IMVDb", f"No videos found for {year}")
        return
    play_videos(videos, year)

def play_videos(videos, session_name):
    # Already shuffle the full list
    random.shuffle(videos)
    
    profile_path = translatePath(ADDON.getAddonInfo('profile'))
    if not os.path.exists(profile_path):
        os.makedirs(profile_path)
    
    list_file = os.path.join(profile_path, 'current_playlist.json')
    with open(list_file, 'w') as f:
        json.dump(videos, f)

    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()

    # Show background progress during resolution as a secondary indicator
    pDialog = xbmcgui.DialogProgressBG()
    pDialog.create('IMVDb', 'Resolving music videos...')

    resolved_count = 0
    max_initial = min(5, len(videos))
    for i in range(max_initial):
        pDialog.update(int((i / max_initial) * 100))
        v = videos[i]
        yt_id = get_youtube_id(v['id'])
        if yt_id:
            plugin_url = f"plugin://plugin.video.youtube/play/?video_id={yt_id}"
            list_item = xbmcgui.ListItem(label=v.get('song_title', 'Unknown'))
            list_item.setArt({'thumb': v.get('image', {}).get('l', '')})
            artists_list = [a['name'] for a in v.get('artists', [])]
            set_listitem_info(list_item, {
                'title': v.get('song_title'), 
                'artist': artists_list, 
                'year': int(v.get('year', 0)),
                'mediatype': 'musicvideo'
            })
            playlist.add(url=plugin_url, listitem=list_item)
            resolved_count += 1
    
    pDialog.close()
    hide_busy()
    
    if resolved_count > 0:
        # Set Window Property as a primary notification for the service
        xbmcgui.Window(10000).setProperty('imvdb_session', str(session_name))
        xbmcgui.Window(10000).setProperty('imvdb_trigger', str(random.random())) # Ensure property change trigger
        
        xbmc.Player().play(playlist)
        # Fallback notification
        xbmc.executebuiltin(f"NotifyAll({ADDON_ID}, playlist_started, {session_name})")
    else:
        xbmcgui.Dialog().ok("IMVDb", "Could not resolve any music video links.")

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    if not params:
        list_menu()
    else:
        action = params.get('action')
        log(f"Router action: {action}")
        if action == 'search_year':
            search_year()
        elif action == 'select_year':
            select_year(params.get('year'))
        elif action == 'search_artist':
            search_artist()
        elif action == 'search_year_exec': # Reserved for future
             pass

if __name__ == '__main__':
    router(sys.argv[2][1:])
