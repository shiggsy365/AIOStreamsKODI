"""
Standalone script to fetch related items from Trakt and posters from AIOStreams.
"""
import requests
import xbmc
import xbmcgui
import xbmcaddon
import xml.etree.ElementTree as ET
import os

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[AIOStreams] {msg}', level)

def get_plugin_setting(setting_id):
    """Get setting from plugin.video.aiostreams."""
    try:
        addon = xbmcaddon.Addon('plugin.video.aiostreams')
        return addon.getSetting(setting_id)
    except:
        # Fallback: Read settings.xml directly if Addon() fails in script context
        try:
            profile_path = xbmc.translatePath('special://userdata/addon_data/plugin.video.aiostreams/settings.xml')
            if os.path.exists(profile_path):
                tree = ET.parse(profile_path)
                root = tree.getroot()
                for setting in root.findall('setting'):
                    if setting.get('id') == setting_id:
                        return setting.text or ''
        except:
            pass
    return ''

def fetch_poster_from_stremio(imdb_id, content_type='movie'):
    """Fetch poster for a specific IMDb ID from Stremio API."""
    try:
        if ':' in imdb_id:
            imdb_id = imdb_id.split(':')[0]
            
        api_type = 'movie' if content_type in ['movie', 'video'] else 'series'
        
        # Hardcoded AIOStreams auth for Stremio API (matches fetch_cast.py)
        user_id = '3301cce2-06c1-4794-ad5b-e44c95f60e9c'
        auth_token = 'eyJpdiI6IkN3cXkreVNITW45QnhJaHU2dHVyM3c9PSIsImVuY3J5cHRlZCI6IitUeVZEUE5ZMHNxMjhOY2drSTJTMW44V0U2UUc5d0Qvd3RKL0REMGdzQzQ9IiwidHlwZSI6ImFpb0VuY3J5cHQifQ'
        
        url = f'https://aiostreams.shiggsy.co.uk/stremio/{user_id}/{auth_token}/meta/{api_type}/{imdb_id}.json'
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        return data.get('meta', {}).get('poster', '')
    except:
        return ''


def fetch_trailer(imdb_id, content_type='movie'):
    """Fetch trailer URL for a specific IMDb ID from Stremio API."""
    try:
        if ':' in imdb_id:
            imdb_id = imdb_id.split(':')[0]
            
        api_type = 'movie' if content_type in ['movie', 'video'] else 'series'
        
        # Hardcoded AIOStreams auth (matches fetch_cast.py)
        user_id = '3301cce2-06c1-4794-ad5b-e44c95f60e9c'
        auth_token = 'eyJpdiI6IkN3cXkreVNITW45QnhJaHU2dHVyM3c9PSIsImVuY3J5cHRlZCI6IitUeVZEUE5ZMHNxMjhOY2drSTJTMW44V0U2UUc5d0Qvd3RKL0REMGdzQzQ9IiwidHlwZSI6ImFpb0VuY3J5cHQifQ'
        
        url = f'https://aiostreams.shiggsy.co.uk/stremio/{user_id}/{auth_token}/meta/{api_type}/{imdb_id}.json'
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        meta = data.get('meta', {})
        
        trailers = []
        if api_type == 'movie':
            trailers = meta.get('trailers', [])
        else:
            trailers = meta.get('trailerStreams', [])
            
        if trailers and isinstance(trailers, list) and len(trailers) > 0:
            # Try to get YouTube ID first
            youtube_id = trailers[0].get('ytId', '') or trailers[0].get('source', '')
            if youtube_id:
                # Return standard plugin:// URL for YouTube
                return f'plugin://plugin.video.youtube/play/?video_id={youtube_id}'
                
        return None
        
    except Exception as e:
        log(f"Error fetching trailer: {e}", xbmc.LOGERROR)
        return None

def fetch_related_from_trakt(imdb_id, content_type='movie'):
    """Fetch related items from Trakt API."""
    try:
        # Get Trakt tokens from plugin
        client_id = get_plugin_setting('trakt_client_id')
        token = get_plugin_setting('trakt_token')
        
        if not client_id:
            log('Trakt client_id missing from plugin settings', xbmc.LOGWARNING)
            return []
            
        log(f'Using Client ID: {client_id[:4]}... Token present: {bool(token)}')
            
        if ':' in imdb_id:
            imdb_id = imdb_id.split(':')[0]
            
        api_type = 'movies' if content_type in ['movie', 'video'] else 'shows'
        
        url = f'https://api.trakt.tv/{api_type}/{imdb_id}/related'
        headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': client_id,
            'User-Agent': 'AIOStreams/3.3.11 (Kodi)'
        }
        
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        log(f'Calling Trakt related: {url}')
        response = requests.get(url, headers=headers, timeout=10)
        
        log(f'Trakt Response: {response.status_code}')
        if response.status_code != 200:
            log(f'Trakt Error Body: {response.text[:200]}', xbmc.LOGERROR)
            
        response.raise_for_status()
        
        items = response.json()
        log(f'Trakt returned {len(items)} items')
        related_list = []
        
        # Limit to 10 items to avoid too many poster fetches
        for i, item in enumerate(items[:10]):
            # Check if item is wrapped (e.g. {'movie': {...}}) or flat
            if 'movie' in item:
                media_type = 'movie'
                media_data = item['movie']
            elif 'show' in item:
                media_type = 'show'
                media_data = item['show']
            else:
                # Flat structure (standard for related endpoint)
                media_type = 'movie' if content_type in ['movie', 'video'] else 'show'
                media_data = item
            
            
            rel_imdb = media_data.get('ids', {}).get('imdb', '')
            if not rel_imdb:
                log(f'Skipping item {i}: No IMDb ID found. Keys: {media_data.get("ids", {}).keys()}', xbmc.LOGWARNING)
                continue
                
            title = media_data.get('title', 'Unknown')
            year = media_data.get('year', '')
            
            # Fetch poster
            try:
                poster = fetch_poster_from_stremio(rel_imdb, media_type)
            except Exception as e:
                log(f'Error fetching poster for {rel_imdb}: {e}', xbmc.LOGERROR)
                poster = ''
            
            # Log successful item processing
            log(f'Processed item {i}: {title} ({year}) -> {rel_imdb}')
            
            related_list.append({
                'imdb': rel_imdb,
                'title': title,
                'year': str(year),
                'poster': poster
            })
            
        log(f'Finished processing. Returning {len(related_list)} valid items.')
        return related_list
        
    except Exception as e:
        log(f'Error in fetch_related_from_trakt: {e}', xbmc.LOGERROR)
        return []

def populate_related_properties(imdb_id, content_type='movie'):
    """Fetch related items and set window properties."""
    log(f'ENTER populate_related_properties with imdb_id={imdb_id}, content_type={content_type}')
    related_items = fetch_related_from_trakt(imdb_id, content_type)
    
    home_window = xbmcgui.Window(10000)
    
    # Clear old properties
    for i in range(1, 11):
        home_window.clearProperty(f'InfoWindow.Related.{i}.Title')
        home_window.clearProperty(f'InfoWindow.Related.{i}.Year')
        home_window.clearProperty(f'InfoWindow.Related.{i}.Thumb')
        home_window.clearProperty(f'InfoWindow.Related.{i}.IMDB')
        
    if related_items:
        log(f'Setting {len(related_items)} related item properties')
        for i, item in enumerate(related_items, 1):
            home_window.setProperty(f'InfoWindow.Related.{i}.Title', item['title'])
            home_window.setProperty(f'InfoWindow.Related.{i}.Year', item['year'])
            home_window.setProperty(f'InfoWindow.Related.{i}.Thumb', item['poster'])
            home_window.setProperty(f'InfoWindow.Related.{i}.IMDB', item['imdb'])
            if i <= 5:
                log(f'Set related item {i}: {item["title"]} ({item["year"]})')
            
    return len(related_items)
