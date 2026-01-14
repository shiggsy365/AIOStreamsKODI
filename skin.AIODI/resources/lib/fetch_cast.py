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
        
        log(f'Successfully fetched {len(cast_list)} cast members from API')
        return cast_list
        
    except requests.exceptions.Timeout:
        log(f'Timeout fetching cast from API for {imdb_id}', xbmc.LOGWARNING)
        return []
    except requests.exceptions.RequestException as e:
        log(f'Error fetching cast from API: {e}', xbmc.LOGERROR)
        return []
    except Exception as e:
        log(f'Unexpected error fetching cast: {e}', xbmc.LOGERROR)
        return []
