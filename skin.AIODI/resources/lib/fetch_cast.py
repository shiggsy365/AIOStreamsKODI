"""
Standalone script to fetch cast data from AIOStreams API.
Can be called from skin context without plugin initialization issues.
"""
import requests
import xbmc


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[AIOStreams] [FetchCast] {msg}', level)


def fetch_cast_from_api(imdb_id, content_type='movie'):
    """
    Fetch cast data directly from AIOStreams Stremio API.
    Returns list of cast members with name, character, and photo.
    """
    try:
        # Strip out any :S:E formatting after the imdb id (e.g. tt23743442:1:1 -> tt23743442)
        if ':' in imdb_id:
            imdb_id = imdb_id.split(':')[0]
            log(f'Cleaned IMDb ID: {imdb_id}')
            
        # Map content types to 'series' for the Stremio API if needed
        api_type = content_type
        if content_type in ['tvshow', 'episode', 'series']:
            api_type = 'series'
        
        log(f'Fetching cast from API for {api_type}: {imdb_id}')
        
        # AIOStreams Stremio API endpoint with auth token
        # Format: https://aiostreams.shiggsy.co.uk/stremio/{user_id}/{auth_token}/meta/{type}/{imdb_id}.json
        user_id = '3301cce2-06c1-4794-ad5b-e44c95f60e9c'
        auth_token = 'eyJpdiI6IkN3cXkreVNITW45QnhJaHU2dHVyM3c9PSIsImVuY3J5cHRlZCI6IitUeVZEUE5ZMHNxMjhOY2drSTJTMW44V0U2UUc5d0Qvd3RKL0REMGdzQzQ9IiwidHlwZSI6ImFpb0VuY3J5cHQifQ'
        
        url = f'https://aiostreams.shiggsy.co.uk/stremio/{user_id}/{auth_token}/meta/{api_type}/{imdb_id}.json'
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract cast from meta.app_extras object
        meta = data.get('meta', {})
        app_extras = meta.get('app_extras', {})
        cast_list = app_extras.get('cast', [])
        
        # Extract Trailer
        trailers = []
        if api_type == 'movie':
             trailers = meta.get('trailers', [])
        else:
             trailers = meta.get('trailerStreams', []) # Some endpoints use this

        # Fallback: Check both if specific one is empty
        if not trailers:
            trailers = meta.get('trailers', []) or meta.get('trailerStreams', [])

        trailer_url = None
        if trailers and isinstance(trailers, list) and len(trailers) > 0:
             # Try explicit Youtube ID first
             youtube_id = trailers[0].get('ytId', '')
             
             # If no ID, check source
             if not youtube_id:
                 source = trailers[0].get('source', '')
                 if 'youtube.com' in source or 'youtu.be' in source:
                     # Attempt to extract ID from URL
                     import re
                     # Matches v=ID or short url /ID
                     match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', source)
                     if match:
                         youtube_id = match.group(1)
                 elif source and not source.startswith('http'):
                     # Assume source IS the ID if it's not a URL
                     youtube_id = source
            
             if youtube_id:
                 trailer_url = f'plugin://plugin.video.youtube/play/?video_id={youtube_id}'

        log(f'Successfully fetched {len(cast_list)} cast members. Trailer found: {bool(trailer_url)} ({trailer_url})')
        return cast_list, trailer_url
        
    except requests.exceptions.Timeout:
        log(f'Timeout fetching cast from API for {imdb_id}', xbmc.LOGWARNING)
        return [], None
    except requests.exceptions.RequestException as e:
        log(f'Error fetching cast from API: {e}', xbmc.LOGERROR)
        return [], None
    except Exception as e:
        log(f'Unexpected error fetching cast: {e}', xbmc.LOGERROR)
        return [], None
