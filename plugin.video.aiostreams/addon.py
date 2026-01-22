import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
from urllib.parse import urlencode, parse_qsl
import requests
import json
import threading
import hashlib
import os
import time
import pickle
from concurrent.futures import ThreadPoolExecutor, as_completed


# IMPORTS OPTIMIZATION: Heavy imports moved to functions
# from resources.lib import trakt (Lazy loaded in functions)
# from resources.lib import network (Moved)
# from resources.lib.router import get_router, action, dispatch, set_default (Moved)

# Import new modules with enhanced architecture
try:
    # Essential imports only
    from resources.lib import ui_helpers, settings_helpers, constants, filters, cache
    from resources.lib.globals import g
    from resources.lib.router import get_router, action, dispatch, set_default
    
    # ProviderManager and GUI helpers are needed somewhat early but let's check optimization
    from resources.lib.providers import ProviderManager, AIOStreamsProvider
    from resources.lib.providers.base import get_provider_manager
    from resources.lib.gui import show_source_select_dialog
    # Clearlogo is needed for init sometimes?
    from resources.lib.clearlogo import clear_clearlogo_cache, get_cached_clearlogo_path, download_and_cache_clearlogo, get_clearlogo_cache_dir
    HAS_MODULES = True
    HAS_NEW_MODULES = True
except Exception as e:
    HAS_MODULES = False
    HAS_NEW_MODULES = False
    xbmc.log(f'[AIOStreams] Failed to import modules: {e}', xbmc.LOGERROR)

# Initialize globals (new pattern)
if HAS_NEW_MODULES:
    try:
        g.init(sys.argv)
        
        # Initialize shared cache directories for multi-profile support
        # Call moved to service.py for efficiency, but kept import for other uses
        from resources.lib.shared_cache import SharedCacheManager
        from resources.lib.ui_helpers import clear_all_window_properties
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to initialize globals: {e}', xbmc.LOGERROR)

# Initialize addon (legacy compatibility)
ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
HANDLE = int(sys.argv[1])

# Initialize provider manager
if HAS_NEW_MODULES:
    try:
        provider_manager = get_provider_manager()
        aiostreams_provider = AIOStreamsProvider()
        provider_manager.register(aiostreams_provider)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to initialize providers: {e}', xbmc.LOGERROR)

# Run initialize logic once per addon execution
# Run initialize logic once per addon execution - MOVED TO SERVICE.PY (Background)
# def initialize():
#     pass



def get_player():
    """Get the current PLAYER instance dynamically to avoid stale references."""
    from resources.lib import monitor
    xbmc.log(f'[AIOStreams] get_player() returning instance: {id(monitor.PLAYER)}', xbmc.LOGDEBUG)
    return monitor.PLAYER

def get_setting(setting_id, default=None):
    """Get addon setting."""
    value = ADDON.getSetting(setting_id)
    return value if value else default


def get_base_url():
    """Get the base URL from settings."""
    url = get_setting('base_url', '')
    
    # Strip /manifest.json if user pasted full URL
    if url.endswith('/manifest.json'):
        url = url[:-14]  # Remove /manifest.json
    
    return url


def get_all_catalogs_action():
    """Get all available catalogs for the Modify Lists feature."""
    xbmcplugin.setPluginCategory(HANDLE, 'All Catalogs')
    xbmcplugin.setContent(HANDLE, 'files')
    
    manifest = get_manifest()
    if not manifest:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    
    for catalog in manifest.get('catalogs', []):
        list_item = xbmcgui.ListItem(label=catalog.get('name', 'Unknown'))
        list_item.setLabel2(catalog.get('type', 'unknown'))
        list_item.setProperty('catalog_id', catalog.get('id', ''))
        list_item.setProperty('content_type', catalog.get('type', ''))
        url = get_url(action='browse_catalog', catalog_id=catalog.get('id'), content_type=catalog.get('type'), catalog_name=catalog.get('name'))
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def get_folder_browser_catalogs_action():
    """Get only the catalogs used in the folder browser (for Widget Manager)."""
    xbmcplugin.setPluginCategory(HANDLE, 'Folder Browser Catalogs')
    xbmcplugin.setContent(HANDLE, 'files')
    
    manifest = get_manifest()
    if not manifest:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    
    # Get only catalogs that are used in the folder browser
    # These are the catalogs shown in series_lists() and movie_lists()
    for catalog in manifest.get('catalogs', []):
        list_item = xbmcgui.ListItem(label=catalog.get('name', 'Unknown'))
        list_item.setLabel2(catalog.get('type', 'unknown'))
        list_item.setProperty('catalog_id', catalog.get('id', ''))
        list_item.setProperty('content_type', catalog.get('type', ''))
        url = get_url(action='browse_catalog', catalog_id=catalog.get('id'), content_type=catalog.get('type'), catalog_name=catalog.get('name'))
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def get_timeout():
    """Get request timeout from settings."""
    try:
        return int(get_setting('timeout', '10'))
    except ValueError:
        return 10


def get_url(**kwargs):
    """Create a URL for calling the plugin recursively from the given set of keyword arguments."""
    return '{}?{}'.format(sys.argv[0], urlencode(kwargs))


# Clearlogo Helpers moved to resources/lib/clearlogo.py



def make_request(url, error_message='Request failed', cache_key=None):
    """Make HTTP request with conditional caching support (ETag/If-None-Match).

    Args:
        url: URL to fetch
        error_message: Error message to display on failure
        cache_key: Optional cache key for conditional requests (format: "type:identifier")

    Returns:
        JSON response data, or cached data on 304, or None on error
    """
    headers = {}

    # Check for cached ETag/Last-Modified headers to enable conditional requests
    if cache_key and HAS_MODULES:
        cached_headers = cache.get_cached_data('http_headers', cache_key, 86400*365)  # 1 year TTL
        if cached_headers:
            if 'etag' in cached_headers:
                headers['If-None-Match'] = cached_headers['etag']
                xbmc.log(f'[AIOStreams] Conditional request with ETag for {cache_key}', xbmc.LOGDEBUG)
            if 'last-modified' in cached_headers:
                headers['If-Modified-Since'] = cached_headers['last-modified']
                xbmc.log(f'[AIOStreams] Conditional request with Last-Modified for {cache_key}', xbmc.LOGDEBUG)

    try:
        response = requests.get(url, headers=headers, timeout=get_timeout())

        # 304 Not Modified - content hasn't changed, use cached data
        if response.status_code == 304:
            xbmc.log(f'[AIOStreams] HTTP 304 Not Modified: Using cached data for {cache_key}', xbmc.LOGDEBUG)
            if cache_key and HAS_MODULES:
                parts = cache_key.split(':', 1)
                if len(parts) == 2:
                    cached_data = cache.get_cached_data(parts[0], parts[1], 86400*365)
                    if cached_data:
                        return cached_data
            # Fallback if cache lookup fails
            xbmc.log(f'[AIOStreams] Warning: 304 received but no cached data found', xbmc.LOGWARNING)
            return None

        response.raise_for_status()
        data = response.json()

        # Cache response headers (ETag/Last-Modified) for future conditional requests
        if cache_key and HAS_MODULES:
            cache_headers = {}
            if 'etag' in response.headers:
                cache_headers['etag'] = response.headers['etag']
                xbmc.log(f'[AIOStreams] Cached ETag for {cache_key}: {response.headers["etag"]}', xbmc.LOGDEBUG)
            if 'last-modified' in response.headers:
                cache_headers['last-modified'] = response.headers['last-modified']
                xbmc.log(f'[AIOStreams] Cached Last-Modified for {cache_key}', xbmc.LOGDEBUG)
            if cache_headers:
                cache.cache_data('http_headers', cache_key, cache_headers)

        return data
    except requests.Timeout:
        xbmcgui.Dialog().notification('AIOStreams', 'Request timed out', xbmcgui.NOTIFICATION_ERROR)
        return None
    except requests.RequestException as e:
        xbmcgui.Dialog().notification('AIOStreams', f'{error_message}: {str(e)}', xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f'[AIOStreams] Request error: {str(e)}', xbmc.LOGERROR)
        return None
    except ValueError:
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid JSON response', xbmcgui.NOTIFICATION_ERROR)
        return None


def get_manifest():
    """Fetch the manifest from AIOStreams with stale-while-revalidate caching.

    Uses HTTP conditional requests (ETag/If-None-Match) to minimize bandwidth:
    - Serves cached data immediately if < 24 hours old
    - For older cache, checks server with If-None-Match (gets 304 if unchanged)
    - Only downloads full manifest if actually changed on server
    """
    base_url = get_base_url()

    # Use base_url as cache key to support multiple user profiles with different manifests
    import hashlib
    cache_key = hashlib.md5(base_url.encode()).hexdigest()[:16]
    full_cache_key = f'manifest:{cache_key}'

    # Check cache first (never expire - rely on conditional requests)
    if HAS_MODULES:
        cached = cache.get_cached_data('manifest', cache_key, 86400*365)  # 1 year
        cache_age = cache.get_cache_age('manifest', cache_key)

        if cached:
            # Fresh cache (< 24 hours) - serve immediately
            if cache_age is not None and cache_age < 86400:
                xbmc.log(f'[AIOStreams] Serving fresh manifest from cache (age: {int(cache_age)}s)', xbmc.LOGDEBUG)
                return cached

            # Stale cache - check server with conditional request
            xbmc.log(f'[AIOStreams] Cache stale (age: {int(cache_age)}s), checking server with conditional request', xbmc.LOGDEBUG)
            manifest = make_request(f"{base_url}/manifest.json",
                                   'Error fetching manifest',
                                   cache_key=full_cache_key)

            if manifest:
                # Server returned new data (200 OK) - cache it
                cache.cache_data('manifest', cache_key, manifest)
                xbmc.log('[AIOStreams] Manifest updated from server', xbmc.LOGINFO)
                return manifest
            else:
                # Request failed or 304 (already handled in make_request)
                # If it was 304, make_request returned cached data
                # If it failed, return stale cache as fallback
                xbmc.log('[AIOStreams] Using stale manifest as fallback', xbmc.LOGDEBUG)
                return cached

    # No cache - fetch fresh
    xbmc.log('[AIOStreams] No cached manifest, fetching fresh', xbmc.LOGDEBUG)
    manifest = make_request(f"{base_url}/manifest.json",
                           'Error fetching manifest',
                           cache_key=full_cache_key)

    if manifest and HAS_MODULES:
        cache.cache_data('manifest', cache_key, manifest)

    return manifest


def search_catalog(query, content_type='movie', skip=0):
    """Search the AIOStreams catalog with pagination."""
    if content_type in ['video', 'youtube'] or 'youtube' in str(content_type):
        youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
        if not youtube_available:
            xbmc.log(f'[AIOStreams] Blocking YouTube search request for "{query}"', xbmc.LOGINFO)
            return {'metas': []}

    base_url = get_base_url()
    catalog_id = '39fe3b0.search'
    url = f"{base_url}/catalog/{content_type}/{catalog_id}/search={query}"
    
    # Add skip parameter for pagination
    if skip > 0:
        url += f"&skip={skip}"
    
    url += ".json"
    
    return make_request(url, 'Search error')


def get_streams(content_type, media_id):
    """Fetch streams for a given media ID."""
    base_url = get_base_url()
    url = f"{base_url}/stream/{content_type}/{media_id}.json"
    xbmc.log(f'[AIOStreams] Requesting streams from: {url}', xbmc.LOGDEBUG)
    result = make_request(url, 'Stream error')
    if result:
        xbmc.log(f'[AIOStreams] Received {len(result.get("streams", []))} streams for {media_id}', xbmc.LOGINFO)
    return result


def get_catalog(content_type, catalog_id, genre=None, skip=0):
    """Fetch a catalog from AIOStreams with 6-hour caching."""
    from resources.lib import trakt
    # Build cache identifier from all parameters
    cache_id = f"{content_type}:{catalog_id}:{genre or 'none'}:{skip}"

    # Check SQL cache first (fastest)
    if HAS_MODULES:
        try:
            db = trakt.get_trakt_db()
            if db:
                cached_sql = db.get_catalog(content_type, catalog_id, genre, skip)
                if cached_sql:
                    xbmc.log(f'[AIOStreams] SQL Cache hit for catalog: {catalog_id}', xbmc.LOGDEBUG)
                    return cached_sql
        except Exception as e:
             xbmc.log(f'[AIOStreams] SQL Cache error for catalog: {e}', xbmc.LOGDEBUG)

    # Check file cache second (legacy)
    if HAS_MODULES:
        cached = cache.get_cached_data('catalog', cache_id, 21600)
        if cached:
            return cached

    # Cache miss, fetch from API
    base_url = get_base_url()

    # Build catalog URL with optional filters
    url_parts = [f"{base_url}/catalog/{content_type}/{catalog_id}"]

    extras = []
    if genre:
        extras.append(f"genre={genre}")
    if skip > 0:
        extras.append(f"skip={skip}")

    if extras:
        url = f"{url_parts[0]}/{'&'.join(extras)}.json"
    else:
        url = f"{url_parts[0]}.json"

    xbmc.log(f'[AIOStreams] Requesting catalog from: {url}', xbmc.LOGDEBUG)
    catalog = make_request(url, 'Catalog error')

    # Cache the result in both tiers
    if catalog and HAS_MODULES:
        # 1. File cache
        cache.cache_data('catalog', cache_id, catalog)
        # 2. SQL cache
        try:
            db = trakt.get_trakt_db()
            if db:
                db.set_catalog(content_type, catalog_id, genre, skip, catalog, 21600)
        except:
            pass

    return catalog


def get_subtitles(content_type, media_id):
    """Fetch subtitles for a given media ID."""
    base_url = get_base_url()
    url = f"{base_url}/subtitles/{content_type}/{media_id}.json"
    xbmc.log(f'[AIOStreams] Requesting subtitles from: {url}', xbmc.LOGINFO)
    return make_request(url, 'Subtitle error')


def get_subtitle_language_filter():
    """Get the user's subtitle language filter preferences."""
    filter_setting = get_setting('subtitle_languages', '')
    if not filter_setting or not filter_setting.strip():
        return None

    # Split by comma and normalize to 3-letter codes
    langs = [lang.strip().lower() for lang in filter_setting.split(',') if lang.strip()]

    # Normalize all to 3-letter codes
    normalized_langs = []
    for lang in langs:
        normalized = normalize_language_to_3letter(lang)
        if normalized and normalized != 'unk':
            normalized_langs.append(normalized)

    return normalized_langs if normalized_langs else None


def filter_subtitles_by_language(subtitles):
    """Filter subtitles based on user's language preferences."""
    language_filter = get_subtitle_language_filter()

    # If no filter is set, return all subtitles
    if not language_filter:
        return subtitles

    filtered = []
    for subtitle in subtitles:
        lang = subtitle.get('lang', '').lower().strip()
        # Normalize the subtitle language to 3-letter code
        normalized_lang = normalize_language_to_3letter(lang)

        # Include if it matches any of the filter languages
        if normalized_lang in language_filter:
            filtered.append(subtitle)
            xbmc.log(f'[AIOStreams] Including subtitle: {normalized_lang} (matches filter)', xbmc.LOGDEBUG)
        else:
            xbmc.log(f'[AIOStreams] Filtering out subtitle: {normalized_lang}', xbmc.LOGDEBUG)

    return filtered


def download_subtitle_with_language(subtitle_url, language, media_id, subtitle_id=None):
    """
    Download subtitle to local cache with AIOStreams branding.
    This creates subtitles named "AIOStreams - ID - LANG" for display in Kodi.
    """
    import os
    import hashlib

    try:
        # Create subtitles cache directory
        addon_data_path = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
        subtitle_cache_dir = os.path.join(addon_data_path, 'subtitles')

        if not xbmcvfs.exists(subtitle_cache_dir):
            xbmcvfs.mkdirs(subtitle_cache_dir)

        # Create unique filename based on media_id and subtitle ID
        # Use hashes to avoid filesystem issues with special characters
        media_hash = hashlib.md5(media_id.encode()).hexdigest()[:8]

        # Use subtitle ID if provided, otherwise fallback to URL hash
        if subtitle_id:
            unique_id = str(subtitle_id)
        else:
            unique_id = hashlib.md5(subtitle_url.encode()).hexdigest()[:6]

        # Normalize language code to 3-letter format
        lang_code = normalize_language_to_3letter(language)

        # Determine subtitle extension from URL or default to .srt
        if subtitle_url.endswith('.vtt'):
            ext = '.vtt'
        else:
            ext = '.srt'

        # Format: "{media_hash}_{unique_id}.AIOStreams - {unique_id} - {lang_code}{ext}"
        # Kodi displays this as "AIOStreams - {unique_id} - {lang_code}" (strips hash and extension)
        # The subtitle_id ensures each subtitle has a unique filename
        subtitle_filename = f"{media_hash}_{unique_id}.AIOStreams - {unique_id} - {lang_code}{ext}"
        subtitle_path = os.path.join(subtitle_cache_dir, subtitle_filename)

        # Download subtitle content
        timeout = get_timeout()
        response = requests.get(subtitle_url, timeout=timeout)
        response.raise_for_status()

        # Write to file
        with open(subtitle_path, 'wb') as f:
            f.write(response.content)

        xbmc.log(f'[AIOStreams] Downloaded subtitle [AIOStreams - {unique_id} - {lang_code}] to: {subtitle_path}', xbmc.LOGINFO)
        return subtitle_path

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error downloading subtitle: {e}', xbmc.LOGERROR)
        # Fall back to original URL
        return subtitle_url


def normalize_language_to_3letter(language):
    """Convert language code to ISO 639-2 (3-letter) format."""
    # Common language mappings to 3-letter codes
    lang_map_3 = {
        # 3-letter codes (already normalized)
        'eng': 'eng', 'spa': 'spa', 'fre': 'fre', 'fra': 'fra', 'ger': 'ger', 'deu': 'deu',
        'ita': 'ita', 'por': 'por', 'rus': 'rus', 'chi': 'chi', 'zho': 'zho',
        'jpn': 'jpn', 'kor': 'kor', 'ara': 'ara', 'hin': 'hin', 'dut': 'dut', 'nld': 'nld',
        'pol': 'pol', 'tur': 'tur', 'swe': 'swe', 'dan': 'dan', 'nor': 'nor',
        'fin': 'fin', 'cze': 'cze', 'ces': 'ces', 'gre': 'gre', 'ell': 'ell',
        'heb': 'heb', 'tha': 'tha', 'vie': 'vie',
        # 2-letter to 3-letter conversions
        'en': 'eng', 'es': 'spa', 'fr': 'fra', 'de': 'deu', 'it': 'ita',
        'pt': 'por', 'ru': 'rus', 'zh': 'zho', 'ja': 'jpn', 'ko': 'kor',
        'ar': 'ara', 'hi': 'hin', 'nl': 'nld', 'pl': 'pol', 'tr': 'tur',
        'sv': 'swe', 'da': 'dan', 'no': 'nor', 'fi': 'fin', 'cs': 'ces',
        'el': 'ell', 'he': 'heb', 'th': 'tha', 'vi': 'vie',
        # Full language names to 3-letter
        'english': 'eng', 'spanish': 'spa', 'french': 'fra', 'german': 'deu',
        'italian': 'ita', 'portuguese': 'por', 'russian': 'rus', 'chinese': 'zho',
        'japanese': 'jpn', 'korean': 'kor', 'arabic': 'ara', 'hindi': 'hin',
        'dutch': 'nld', 'polish': 'pol', 'turkish': 'tur', 'swedish': 'swe',
        'danish': 'dan', 'norwegian': 'nor', 'finnish': 'fin', 'czech': 'ces',
        'greek': 'ell', 'hebrew': 'heb', 'thai': 'tha', 'vietnamese': 'vie',
    }

    # Try to get language code
    lang_lower = language.lower().strip()

    # If it's already a 3-letter code, return as-is if valid
    if len(lang_lower) == 3 and lang_lower in lang_map_3:
        return lang_map_3[lang_lower]

    # Try to find in mapping
    return lang_map_3.get(lang_lower, lang_lower[:3] if len(lang_lower) >= 3 else 'unk')


def format_date_with_ordinal(date_str):
    """Format YYYY-MM-DD date to 'dd mmm yyyy' format (e.g. 19 Jan 2026)."""
    import datetime
    try:
        if not date_str:
            return ''
            
        # Extract YYYY-MM-DD if ISO format
        if 'T' in date_str:
            date_str = date_str.split('T')[0]
            
        dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%d %b %Y')
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error formatting date {date_str}: {e}', xbmc.LOGDEBUG)
        return date_str


def get_metadata_ttl(meta_data):
    """Determine appropriate cache TTL based on content age.

    Args:
        meta_data: Metadata dict from API (must contain 'meta' key)

    Returns:
        TTL in seconds
    """
    from datetime import datetime

    try:
        meta = meta_data.get('meta', {})
        year = meta.get('year')

        if year:
            current_year = datetime.now().year

            # Recent/current year content may get metadata updates (cast, artwork, etc.)
            if year >= current_year:
                return 86400 * 7  # 7 days

            # Last year's content - moderate refresh
            elif year >= current_year - 1:
                return 86400 * 30  # 30 days

        # Older content is stable - extended cache
        return 86400 * 90  # 90 days

    except:
        # Default to 30 days on any error
        return 86400 * 30


def get_meta(content_type, meta_id):
    """Fetch metadata for a show or movie with optimized TTL caching.

    Cache TTL varies based on content age:
    - Current year: 7 days (metadata may be updated)
    - Last year: 30 days
    - Older: 90 days (metadata is stable)
    """
    from resources.lib import trakt
    # 1. Check SQL cache first (fastest)
    if HAS_MODULES:
        try:
            db = trakt.get_trakt_db()
            if db:
                # Initial check with long TTL (handled by DB expires column)
                cached_sql = db.get_meta(content_type, meta_id)
                if cached_sql:
                    xbmc.log(f'[AIOStreams] SQL Metadata cache hit for {meta_id}', xbmc.LOGDEBUG)
                    # Ensure clearlogo is cached even on metadata hit
                    _ensure_clearlogo_cached(cached_sql, content_type, meta_id)
                    return cached_sql
        except:
            pass

    # 2. Check file-based cache (middle tier)
    if HAS_MODULES:
        cached = cache.get_cached_meta(content_type, meta_id, ttl_seconds=86400*365)
        if cached:
            # Calculate appropriate TTL based on content
            ttl = get_metadata_ttl(cached)

            # Re-check cache with calculated TTL
            cached = cache.get_cached_meta(content_type, meta_id, ttl_seconds=ttl)
            if cached:
                xbmc.log(f'[AIOStreams] File Metadata cache hit for {meta_id} (TTL: {ttl//86400} days)', xbmc.LOGDEBUG)
                # Ensure clearlogo is cached even on metadata hit
                _ensure_clearlogo_cached(cached, content_type, meta_id)
                return cached

    # Cache miss, fetch from API
    base_url = get_base_url()
    url = f"{base_url}/meta/{content_type}/{meta_id}.json"
    xbmc.log(f'[AIOStreams] Requesting meta from: {url}', xbmc.LOGINFO)
    result = make_request(url, 'Meta error')

    # Store in cache
    if HAS_MODULES and result:
        ttl = get_metadata_ttl(result)
        # 1. File cache
        cache.cache_meta(content_type, meta_id, result)
        # 2. SQL cache
        try:
            db = trakt.get_trakt_db()
            if db:
                db.set_meta(content_type, meta_id, result, ttl)
        except:
            pass
        xbmc.log(f'[AIOStreams] Cached metadata for {meta_id} (TTL: {ttl//86400} days)', xbmc.LOGDEBUG)
        
        # 3. Cache clearlogo if present
        if result.get('meta', {}).get('logo'):
            clearlogo_url = result['meta']['logo']
            try:
                download_and_cache_clearlogo(clearlogo_url, content_type, meta_id)
            except Exception as e:
                xbmc.log(f'[AIOStreams] Error caching clearlogo during metadata fetch: {e}', xbmc.LOGDEBUG)

    return result


def _ensure_clearlogo_cached(meta_item, content_type, meta_id):
    """Ensure clearlogo is cached locally if present in metadata.
    
    This is called to handle cases where the clearlogo file might 
    be missing or was never downloaded.
    """
    try:
        if not meta_item or not isinstance(meta_item, dict):
            return
            
        # Handle both full response structure {'meta': {...}} and direct item {...}
        meta = meta_item.get('meta')
        if not meta or not isinstance(meta, dict):
            meta = meta_item
            
        clearlogo_url = meta.get('logo')
        if clearlogo_url:
            # Check if already cached (fast check)
            if not get_cached_clearlogo_path(content_type, meta_id):
                # Download and cache (will only happen if missing)
                xbmc.log(f'[AIOStreams] Clearlogo missing for item {meta_id}, downloading in background...', xbmc.LOGDEBUG)
                # Run in background to avoid blocking UI too much
                thread = threading.Thread(target=download_and_cache_clearlogo, 
                                          args=(clearlogo_url, content_type, meta_id))
                thread.daemon = True
                thread.start()
    except:
        pass


def fetch_metadata_parallel(items, content_type='movie'):
    """Fetch metadata for a list of items using parallel execution.
    
    Args:
        items: List of dicts, each needing 'ids' dict with 'imdb' or 'tmdb'
        content_type: 'movie' or 'series'
        
    Returns:
        Dict mapping item_id -> metadata_dict
    """
    if not items:
        return {}
        
    results = {}
    
    def fetch_single(item):
        try:
            ids = item.get('ids', {})
            item_id = ids.get('imdb') or ids.get('tmdb')
            if not item_id:
                # Try fallback for simple dicts
                item_id = item.get('imdb_id')
                
            if not item_id:
                return None
            
            # Create a localized DB connection/check if necessary or rely on safe get_meta
            # get_meta handles its own DB connections safely
            meta_result = get_meta(content_type, item_id)
            
            if meta_result and 'meta' in meta_result:
                return (item_id, meta_result['meta'])
            return None
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in fetch_single: {e}', xbmc.LOGERROR)
            return None

    # Use thread pool for parallel fetching
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_single, item) for item in items]
        
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results[result[0]] = result[1]
            except:
                pass
                
    return results


def create_listitem_with_context(meta, content_type, action_url):
    """Create ListItem with full metadata, artwork, and context menus."""
    from resources.lib import trakt
    title = meta.get('name', 'Unknown')
    list_item = xbmcgui.ListItem(label=title)
    
    # Use InfoTagVideo instead of deprecated setInfo
    info_tag = list_item.getVideoInfoTag()
    info_tag.setTitle(title)
    info_tag.setPlot(meta.get('description', ''))
    
    # Set properties for Skin access (crucial for Search Info)
    list_item.setProperty('id', str(meta.get('id', '')))
    list_item.setProperty('content_type', str(content_type))
    
    # Set genres
    genres = meta.get('genres', [])
    if genres:
        info_tag.setGenres(genres)
    
    # Add runtime (handle "2h16min", "48min", "120" formats)
    runtime = meta.get('runtime', '')
    if runtime:
        try:
            runtime_str = str(runtime).lower()
            total_minutes = 0

            # Handle "2h16min" format
            if 'h' in runtime_str:
                parts = runtime_str.split('h')
                hours = int(parts[0].strip())
                total_minutes = hours * 60
                if len(parts) > 1 and parts[1]:
                    mins = parts[1].replace('min', '').replace('minutes', '').strip()
                    if mins:
                        total_minutes += int(mins)
            else:
                # Handle "48min" or "120" format
                mins = runtime_str.replace('min', '').replace('minutes', '').strip()
                total_minutes = int(mins)

            if total_minutes > 0:
                info_tag.setDuration(total_minutes * 60)  # Convert to seconds
        except:
            pass

    # Add release date/premiered - use 'released' field with full ISO date
    released = meta.get('released', '')
    if released:
        try:
            # Extract date in YYYY-MM-DD format from ISO date
            premiered_date = released.split('T')[0]  # "2008-01-20T12:00:00.000Z" -> "2008-01-20"
            info_tag.setPremiered(premiered_date)
            
            # Format and set AiredDate for metadata display (dd mmm yyyy)
            formatted_date = format_date_with_ordinal(premiered_date)
            list_item.setProperty('AiredDate', formatted_date)
            # Also set as label2 for list views
            list_item.setLabel2(formatted_date)
            
            # Extract year
            year = premiered_date[:4]
            info_tag.setYear(int(year))
        except:
            pass
    elif meta.get('releaseInfo'):
        # Fallback to releaseInfo if released not available
        release_info = str(meta.get('releaseInfo', ''))
        try:
            # Extract first year from "2008-2013" or "2008"
            year = release_info.split('-')[0].strip()
            if len(year) == 4:
                info_tag.setYear(int(year))
        except:
            pass

    # Add year if provided separately
    if meta.get('year') and not released:
        try:
            info_tag.setYear(int(meta['year']))
        except:
            pass

    # Add rating - AIOStreams provides imdbRating as string
    imdb_rating = meta.get('imdbRating', '')
    if imdb_rating:
        try:
            info_tag.setRating(float(imdb_rating), votes=0, defaultt=True)
            info_tag.setIMDBNumber(meta.get('imdb_id', meta.get('id', '')))
        except:
            pass

    # Get app_extras once for multiple uses
    app_extras = meta.get('app_extras', {})

    # Add certification/MPAA - check app_extras first, then top level
    certification = app_extras.get('certification', '') or meta.get('certification', '') or meta.get('mpaa', '')
    if certification:
        info_tag.setMpaa(str(certification))

    # Add country/studio
    country = meta.get('country', '')
    if country:
        info_tag.setCountries([str(country)])
        # Also set as studio for lack of better field
        info_tag.setStudios([str(country).upper()])

    # Add cast - try AIOStreams metadata first, then Trakt
    cast_list = []
    aio_cast = app_extras.get('cast', [])

    if aio_cast:
        # Transform AIOStreams cast format to Kodi Actor objects
        for idx, person in enumerate(aio_cast):
            name = person.get('name', '')
            role = person.get('character', '')  # AIOStreams uses 'character' not 'role'
            thumbnail = person.get('photo', '')  # AIOStreams uses 'photo' not 'thumbnail'

            # Create xbmc.Actor object
            actor = xbmc.Actor(name, role, idx, thumbnail)
            cast_list.append(actor)

    # Only use cast from AIOStreams (no Trakt API calls to avoid rate limiting)
    if cast_list:
        info_tag.setCast(cast_list)
        
        # Also set window properties for custom info window (first 5 cast members)
        window = xbmcgui.Window(10000)  # Home window
        for i in range(1, 6):
            if i <= len(aio_cast):
                cast_member = aio_cast[i-1]
                window.setProperty(f'AIOStreams.Cast.{i}.Name', cast_member.get('name', ''))
                window.setProperty(f'AIOStreams.Cast.{i}.Role', cast_member.get('character', ''))
                window.setProperty(f'AIOStreams.Cast.{i}.Thumb', cast_member.get('photo', ''))
            else:
                # Clear if no more cast
                window.clearProperty(f'AIOStreams.Cast.{i}.Name')
                window.clearProperty(f'AIOStreams.Cast.{i}.Role')
                window.clearProperty(f'AIOStreams.Cast.{i}.Thumb')

    # Add directors - try app_extras first (array format), then top level (comma-separated string)
    directors = app_extras.get('directors', [])
    if directors:
        # app_extras.directors is already a list of dicts with 'name' field
        director_names = [d.get('name', '') for d in directors if d.get('name')]
        if director_names:
            info_tag.setDirectors(director_names)
    elif meta.get('director'):
        # Fallback to top-level director field (comma-separated string)
        director_str = meta.get('director', '')
        if director_str:
            # Split comma-separated directors
            directors_list = [d.strip() for d in str(director_str).split(',') if d.strip()]
            if directors_list:
                info_tag.setDirectors(directors_list)

    # Add writers - try app_extras first (array format), then top level (comma-separated string)
    writers = app_extras.get('writers', [])
    if writers:
        # app_extras.writers is already a list of dicts with 'name' field
        writer_names = [w.get('name', '') for w in writers if w.get('name')]
        if writer_names:
            info_tag.setWriters(writer_names)
    elif meta.get('writer'):
        # Fallback to top-level writer field (comma-separated string)
        writer_str = meta.get('writer', '')
        if writer_str:
            # Split comma-separated writers
            writers_list = [w.strip() for w in str(writer_str).split(',') if w.strip()]
            if writers_list:
                info_tag.setWriters(writers_list)
    
    # Set media type
    if content_type == 'movie':
        info_tag.setMediaType('movie')
    elif content_type == 'series':
        info_tag.setMediaType('tvshow')
    
    # Check if watched in Trakt and add overlay/properties
    if HAS_MODULES and trakt.get_access_token():
        item_id = meta.get('id', '')
        if item_id:
            try:
                # Use thread-local DB connection for efficiency
                db = trakt.get_trakt_db()
                if db:
                    # Check watched status using local DB directly with IMDb ID
                    is_watched = db.is_imdb_watched(item_id, content_type)
                    if is_watched:
                        info_tag.setPlaycount(1)
                        list_item.setProperty('WatchedOverlay', 'indicator_watched.png')
                        list_item.setProperty('watched', 'true')
                    
                    # Check for bookmarks (playback progress)
                    bookmark = db.get_bookmark(imdb_id=item_id)
                    if bookmark and bookmark.get('percent_played', 0) > 0:
                        percent = bookmark['percent_played']
                        list_item.setProperty('PercentPlayed', str(int(percent)))
                        info_tag.setPercentPlayed(float(percent))
                        # Set StartOffset for Kodi's internal resume prompt
                        resume_time = bookmark.get('resume_time', 0)
                        if resume_time > 0:
                            list_item.setProperty('StartOffset', str(resume_time))
            except Exception as e:
                xbmc.log(f'[AIOStreams] Error setting watched/bookmark status for {item_id}: {e}', xbmc.LOGDEBUG)
    
    # Set artwork
    art = {}
    if meta.get('poster'):
        art['poster'] = meta['poster']
        art['thumb'] = meta['poster']
    if meta.get('background'):
        art['fanart'] = meta['background']
    logo_url = meta.get('logo')
    if logo_url and isinstance(logo_url, str) and logo_url.lower() != 'none' and logo_url.lower().startswith('http'):
        # Try to use cached clearlogo first
        item_id = meta.get('id', '')
        cached_clearlogo = get_cached_clearlogo_path(content_type, item_id) if item_id else None
        
        if cached_clearlogo:
            art['clearlogo'] = cached_clearlogo
            art['logo'] = cached_clearlogo
            if content_type == 'series':
                art['tvshow.clearlogo'] = cached_clearlogo
        else:
            # Fallback to URL and trigger background download
            art['clearlogo'] = logo_url
            art['logo'] = logo_url
            if content_type == 'series':
                art['tvshow.clearlogo'] = logo_url
            _ensure_clearlogo_cached(meta, content_type, item_id)
            
    if art:
        list_item.setArt(art)
    
    # Build context menu based on content type
    context_menu = []

    item_id = meta.get('id', '')
    title = meta.get('name', 'Unknown')
    poster = meta.get('poster', '')
    fanart = meta.get('background', '')
    # Use the actual clearlogo being used (cached path or URL)
    clearlogo = art.get('clearlogo', meta.get('logo', ''))

    if content_type == 'movie':
        # Movie context menu: Scrape Streams, View Trailer, Mark as Watched, Watchlist
        context_menu.append(('[COLOR lightcoral]Scrape Streams[/COLOR]', f'RunPlugin({get_url(action="show_streams", content_type="movie", media_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)})'))

        # Add trailer if available
        trailers = meta.get('trailers', [])
        # xbmc.log(f'[AIOStreams] Movie Trailers found: {trailers}', xbmc.LOGDEBUG)
        if trailers and isinstance(trailers, list) and len(trailers) > 0:
            youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
            youtube_id = trailers[0].get('ytId', '') or trailers[0].get('source', '')
            if youtube_id and youtube_available:
                trailer_url = f'https://www.youtube.com/watch?v={youtube_id}'
                info_tag.setTrailer(trailer_url)
                play_url = f'plugin://plugin.video.youtube/play/?video_id={youtube_id}'
                context_menu.append(('[COLOR lightcoral]View Trailer[/COLOR]', f'PlayMedia({play_url})'))

        # Trakt context menus if authorized
        if HAS_MODULES and trakt.get_access_token() and item_id:
            db = trakt.get_trakt_db()
            
            # OPTIMIZATION: Use local DB for Watched status
            is_watched = False
            if db:
                is_watched = db.is_imdb_watched(item_id, content_type)

            if is_watched:
                context_menu.append(('[COLOR lightcoral]Mark Movie As Unwatched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_unwatched", media_type=content_type, imdb_id=item_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Movie As Watched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_watched", media_type=content_type, imdb_id=item_id)})'))

            # OPTIMIZATION: Use local DB for Watchlist
            is_in_watchlist = False
            if db:
                is_in_watchlist = db.is_imdb_in_watchlist(item_id, content_type)

            if is_in_watchlist:
                context_menu.append(('[COLOR lightcoral]Remove from Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_remove_watchlist", media_type=content_type, imdb_id=item_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Add to Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_add_watchlist", media_type=content_type, imdb_id=item_id)})'))

    elif content_type == 'series':
        # Show context menu: View Trailer, Mark as Watched, Watchlist
        # Add trailer if available
        trailers = meta.get('trailerStreams', [])
        # xbmc.log(f'[AIOStreams] Series Trailers found: {trailers}', xbmc.LOGDEBUG)
        if trailers and isinstance(trailers, list) and len(trailers) > 0:
            youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
            youtube_id = trailers[0].get('ytId', '') or trailers[0].get('source', '')
            if youtube_id and youtube_available:
                trailer_url = f'https://www.youtube.com/watch?v={youtube_id}'
                info_tag.setTrailer(trailer_url)
                play_url = f'plugin://plugin.video.youtube/play/?video_id={youtube_id}'
                context_menu.append(('[COLOR lightcoral]View Trailer[/COLOR]', f'PlayMedia({play_url})'))

        # Trakt context menus if authorized
        # Trakt context menus if authorized
        if HAS_MODULES and trakt.get_access_token() and item_id:
            # OPTIMIZATION: Use local DB only
            db = trakt.get_trakt_db()
            
            # Check if show is fully watched using local DB
            is_watched = False
            if db:
                progress = db.get_imdb_show_progress(item_id)
                if progress:
                    aired = progress.get('aired', 0)
                    completed = progress.get('completed', 0)
                    is_watched = aired > 0 and aired == completed

            if is_watched:
                context_menu.append(('[COLOR lightcoral]Mark Show As Unwatched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_unwatched", media_type=content_type, imdb_id=item_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Show As Watched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_watched", media_type=content_type, imdb_id=item_id)})'))

            # Stop Watching (Drop) and Unhide options for shows
            if content_type in ['show', 'series', 'tvshow']:
                context_menu.append(('[COLOR lightcoral]Stop Watching (Drop) Trakt[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_hide_from_progress", media_type="series", imdb_id=item_id)})'))
                context_menu.append(('[COLOR lightgreen]Resume Watching (Unhide) Trakt[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_unhide_from_progress", media_type="series", imdb_id=item_id)})'))

            # OPTIMIZATION: Use local DB for Watchlist
            is_in_watchlist = False
            # Reuse db from earlier in this block (lines ~1009)
            if db:
                is_in_watchlist = db.is_imdb_in_watchlist(item_id, content_type)

            if is_in_watchlist:
                context_menu.append(('[COLOR lightcoral]Remove from Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_remove_watchlist", media_type=content_type, imdb_id=item_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Add to Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_add_watchlist", media_type=content_type, imdb_id=item_id)})'))

    list_item.addContextMenuItems(context_menu)

    # Check watched status - Already handled by Direct Injection above!
    # No need to call trakt.is_watched again which might hit API
    return list_item


def index():
    """Main menu."""
    xbmcplugin.setPluginCategory(HANDLE, 'AIOStreams')
    xbmcplugin.setContent(HANDLE, 'videos')
    
    # Create menu items
    list_items = [
        {
            'label': '[B]Search (Movies & TV Shows)[/B]',
            'url': get_url(action='search', content_type='both'),
            'is_folder': True,
            'icon': 'DefaultAddonsSearch.png'
        },
        {
            'label': '[B]Search Movies[/B]',
            'url': get_url(action='search', content_type='movie'),
            'is_folder': True,
            'icon': 'DefaultMovies.png'
        },
        {
            'label': '[B]Search TV Shows[/B]',
            'url': get_url(action='search', content_type='series'),
            'is_folder': True,
            'icon': 'DefaultTVShows.png'
        },
        {
            'label': 'Movie Lists',
            'url': get_url(action='movie_lists'),
            'is_folder': True,
            'icon': 'DefaultMovies.png'
        },
        {
            'label': 'Series Lists',
            'url': get_url(action='series_lists'),
            'is_folder': True,
            'icon': 'DefaultTVShows.png'
        }
    ]
    
    for item in list_items:
        list_item = xbmcgui.ListItem(label=item['label'])
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(item['label'])
        list_item.setArt({'icon': item['icon']})
        xbmcplugin.addDirectoryItem(HANDLE, item['url'], list_item, item['is_folder'])
    
    xbmcplugin.endOfDirectory(HANDLE)


def cancel_all_background_tasks(active=True):
    """
    Cancel ALL background tasks to prioritize search/UI responsiveness.
    Sets a window property for the service to see.
    """
    try:
        win = xbmcgui.Window(10000)
        if active:
            # Tell service to pause sync/tasks
            win.setProperty('AIOStreams.InternalSearchActive', 'true')
            # Skin might also have set AIOStreams.SearchActive
            
            # Clear the reload token to stop any "storm" already in progress
            xbmc.executebuiltin('Skin.ClearString(WidgetReloadToken)')
            # Clear the current queue immediately
            from service import get_task_queue
            get_task_queue().clear()
            xbmc.log('[AIOStreams] Internal Search started - Background tasks suppressed and tokens cleared', xbmc.LOGINFO)
        else:
            win.clearProperty('AIOStreams.InternalSearchActive')
            # Clear reload token to stop any pending "storm"
            xbmc.executebuiltin('Skin.ClearString(WidgetReloadToken)')
            xbmc.log('[AIOStreams] Internal Search finished - Local suppression cleared', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error managing background tasks: {e}', xbmc.LOGDEBUG)


def search():
    """Handle search input."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params.get('content_type', 'both')  # Default to both
    query = params.get('query', '').strip()  # Get query and strip whitespace
    skip = int(params.get('skip', 0))
    
    win = xbmcgui.Window(10000)
    cancel_all_background_tasks(True)

    # Get search query from user if not provided or empty
    if not query:
        keyboard = xbmcgui.Dialog().input('Search', type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            # User cancelled - close the directory properly
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return
        query = keyboard.strip()

    # If content_type is 'both', use unified search directly
    if content_type == 'both':
        try:
            search_unified_internal(query)
        finally:
            cancel_all_background_tasks(False)
        return

    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Searching...')

    # Perform search
    results = search_catalog(query, content_type, skip=skip)
    progress.close()

    if not results or 'metas' not in results or len(results['metas']) == 0:
        # No results found - Set count to 0
        if content_type == 'movie':
            win.setProperty('GlobalSearch.MoviesCount', '0')
        elif content_type in ['tvshows', 'series']:
            win.setProperty('GlobalSearch.SeriesCount', '0')
        elif content_type in ['video', 'youtube']:
            win.setProperty('GlobalSearch.YoutubeCount', '0')
            
        xbmc.log(f'[AIOStreams] Search returned no results for "{query}"', xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
        return
    
    # Apply filters
    if HAS_MODULES and filters:
        results['metas'] = filters.filter_items(results['metas'])
    
    xbmcplugin.setPluginCategory(HANDLE, f'Search: {query}')
    xbmcplugin.setContent(HANDLE, 'movies' if content_type == 'movie' else 'tvshows')
    
    # Calculate counts
    # Only update the property for the current content type to avoid overwriting others
    if content_type == 'movie':
        win.setProperty('GlobalSearch.MoviesCount', str(len(results['metas'])))
    elif content_type == 'tvshows' or content_type == 'series':
        win.setProperty('GlobalSearch.SeriesCount', str(len(results['metas'])))
    elif content_type == 'video' or 'youtube' in str(content_type): # Broad check for youtube
        win.setProperty('GlobalSearch.YoutubeCount', str(len(results['metas'])))
    
    # Display search results
    for meta in results['metas']:
        item_id = meta.get('id')
        item_type = meta.get('type', content_type)

        # Determine if this is a series or movie
        if item_type == 'series':
            # For series, drill down to seasons
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        elif content_type in ['video', 'youtube'] or 'youtube' in str(item_type):
            # For YouTube results, check if it's a folder (channel/playlist) or a playable video
            # YouTube API returns different types which the YouTube plugin handles
            # Folders have 'url' that contains channel/playlist paths
            item_url = meta.get('url', '')
            item_name = meta.get('name', '')
            
            # Detect if this is a folder item (channel/playlist)
            is_youtube_folder = (
                '/channel/' in item_url or
                '/playlist/' in item_url or
                'Channels' in item_name or
                'Playlists' in item_name or
                meta.get('mediatype') in ['channel', 'playlist']
            )
            
            if is_youtube_folder:
                youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
                if not youtube_available:
                    continue
                # Use a custom action to close the dialog before opening the folder
                # This fixes the "Activate of window refused because there are active modal dialogs" error
                item_url = item_url if item_url else meta.get('id', '')
                url = get_url(action='open_youtube_folder', url=item_url)
                is_folder = False # Treat as actionable item to trigger our plugin logic
                xbmc.log(f'[AIOStreams] YouTube folder detected (custom action): {item_name}', xbmc.LOGDEBUG)
            else:
                # It's a playable video
                title = meta.get('name', 'Unknown')
                poster = meta.get('poster', '')
                fanart = meta.get('background', '')
                clearlogo = meta.get('logo', '')
                url = get_url(action='play', content_type='video', imdb_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
                is_folder = False
        else:
            # For movies, make them playable directly
            title = meta.get('name', 'Unknown')
            poster = meta.get('poster', '')
            fanart = meta.get('background', '')
            clearlogo = meta.get('logo', '')
            url = get_url(action='play', content_type='movie', imdb_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)

        # Set IsPlayable property only for non-folder items
        if not is_folder and 'open_youtube_folder' not in url:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)
    
    cancel_all_background_tasks(False)
    
    # Check if next page likely exists based on result count
    # Default limit is usually 20 items per page
    if len(results['metas']) >= 20:
        # Next page likely exists, show "Load More"
        list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
        next_skip = skip + 20
        url = get_url(action='search', content_type=content_type, query=query, skip=next_skip)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def search_unified_internal(query):
    """Internal unified search. Go directly to unified results."""
    # We no longer show a selection dialog to avoid interrupting the user flow
    search_all_results(query)


def search_by_tab(query, content_type, is_widget=False):
    """Search with tab-specific content type with navigation tabs."""
    xbmcplugin.setPluginCategory(HANDLE, f'Search {content_type.title()}: {query}')

    # Set proper content type for poster view
    xbmcplugin.setContent(HANDLE, 'movies' if content_type == 'movie' else 'tvshows')

    # Add navigation tabs at the top (unless widget)
    if not is_widget:
        add_tab_switcher(query, content_type)

    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    content_label = 'TV shows' if content_type == 'series' else f'{content_type}s'
    progress.create('AIOStreams', f'Searching {content_label}...')

    # Perform search
    results = search_catalog(query, content_type, skip=0)
    progress.close()

    if not results or 'metas' not in results or len(results['metas']) == 0:
        # Check if we were interrupted or if it's a legitimate "no results"
        # We check both global and internal flags
        win = xbmcgui.Window(10000)
        search_active = win.getProperty('AIOStreams.SearchActive') == 'true' or \
                        win.getProperty('AIOStreams.InternalSearchActive') == 'true'
        
        if not search_active:
            # No results found - offer to try again in case of typo
            dialog = xbmcgui.Dialog()
            retry = dialog.yesno(
                'No Results Found',
                f'No {content_type}s found for "{query}".',
                'Check spelling and try again?',
                nolabel='Cancel',
                yeslabel='Try Again'
            )
            if retry:
                # Let user correct the search query
                keyboard = dialog.input('Search', query, type=xbmcgui.INPUT_ALPHANUM)
                if keyboard and keyboard.strip():
                    # Recursively call unified search with corrected query
                    corrected_query = keyboard.strip()
                    xbmc.log(f'[AIOStreams] Retrying search with corrected query: {corrected_query}', xbmc.LOGINFO)
                    xbmc.executebuiltin(f'Container.Update({get_url(action="search", content_type="both", query=corrected_query)})')
        else:
            xbmc.log('[AIOStreams] Search returned no results during active suppression - skipping modal dialog', xbmc.LOGINFO)
            
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # Apply filters
    items = results['metas']
    if HAS_MODULES and filters:
        items = filters.filter_items(items)

    # Add results
    for meta in items:
        item_id = meta.get('id')

        if content_type == 'series':
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        else:
            title = meta.get('name', 'Unknown')
            poster = meta.get('poster', '')
            fanart = meta.get('background', '')
            clearlogo = meta.get('logo', '')
            url = get_url(action='play', content_type='movie', imdb_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    # Load more if available (heuristic check)
    if items and len(items) >= 20:
        list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
        next_skip = 20
        url = get_url(action='search_tab', content_type=content_type, query=query, skip=next_skip)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    xbmcplugin.endOfDirectory(HANDLE)


def add_tab_switcher(query, current_tab):
    """Add tab navigation buttons at the top of search results."""
    tabs = [
        ('Movies', 'movie', '●'),
        ('TV Shows', 'series', '●'),
        ('All', 'both', '●')
    ]

    for label, tab_type, icon in tabs:
        if tab_type == current_tab:
            # Current tab - highlighted
            item_label = f'[B][COLOR lightblue]{icon} {label.upper()}[/COLOR][/B]'
        else:
            # Other tabs - clickable
            item_label = f'[COLOR grey]{icon} {label}[/COLOR]'

        list_item = xbmcgui.ListItem(label=item_label)
        list_item.setProperty('IsPlayable', 'false')
        
        # Set icons to avoid generic folder look
        icon = 'DefaultAddonsSearch.png' if tab_type == 'both' else ('DefaultMovies.png' if tab_type == 'movie' else 'DefaultTVShows.png')
        list_item.setArt({
            'icon': icon,
            'thumb': icon,
            'poster': icon
        })
        
        # Add metadata to fill skin's info panel
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(label)
        info_tag.setPlot(f"Switch view to {label} results for '{query}'")

        if tab_type != current_tab:
            if tab_type == 'both':
                url = get_url(action='search_tab', content_type='both', query=query)
            else:
                url = get_url(action='search_tab', content_type=tab_type, query=query)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, '', list_item, False)


def search_all_results(query):
    """Show all results (movies and TV shows) in one view with category headers."""
    xbmcplugin.setPluginCategory(HANDLE, f'Search: {query}')
    xbmcplugin.setContent(HANDLE, 'videos')

    # Add navigation tabs at the top for easy filtering
    add_tab_switcher(query, 'both') # Changed from add_search_tabs to add_tab_switcher as per existing code

    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Searching movies and TV shows...')

    # Search both
    progress.update(25, 'Searching movies...')
    movie_results = search_catalog(query, 'movie', skip=0)

    progress.update(50, 'Searching TV shows...')
    series_results = search_catalog(query, 'series', skip=0)
    progress.close()

    # Movies Section
    if movie_results and 'metas' in movie_results and len(movie_results['metas']) > 0:
        movies = movie_results['metas']
        if HAS_MODULES and filters:
            movies = filters.filter_items(movies)

        if movies:
            # Add Movies Header
            header = xbmcgui.ListItem(label='[B][COLOR lightblue]─── MOVIES ───[/COLOR][/B]')
            header.setProperty('IsPlayable', 'false')
            header.setArt({'icon': 'DefaultMovies.png', 'thumb': 'DefaultMovies.png'})
            info_tag = header.getVideoInfoTag()
            info_tag.setTitle("MOVIES")
            info_tag.setPlot(f"Found {len(movies)} movie results for '{query}'")
            xbmcplugin.addDirectoryItem(HANDLE, '', header, False)

            for meta in movies[:10]:
                item_id = meta.get('id')
                title = meta.get('name', 'Unknown')
                poster = meta.get('poster', '')
                fanart = meta.get('background', '')
                clearlogo = meta.get('logo', '')
                url = get_url(action='play', content_type='movie', imdb_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
                list_item = create_listitem_with_context(meta, 'movie', url)
                list_item.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)

            if len(movies) > 10:
                list_item = xbmcgui.ListItem(label=f'[COLOR yellow]   » View All Movies ({len(movies)} results)[/COLOR]')
                url = get_url(action='search_tab', content_type='movie', query=query)
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    # TV Shows Section
    if series_results and 'metas' in series_results and len(series_results['metas']) > 0:
        shows = series_results['metas']
        if HAS_MODULES and filters:
            shows = filters.filter_items(shows)

        if shows:
            # Add TV Shows Header
            header = xbmcgui.ListItem(label='[B][COLOR lightblue]─── TV SHOWS ───[/COLOR][/B]')
            header.setProperty('IsPlayable', 'false')
            header.setArt({'icon': 'DefaultTVShows.png', 'thumb': 'DefaultTVShows.png'})
            info_tag = header.getVideoInfoTag()
            info_tag.setTitle("TV SHOWS")
            info_tag.setPlot(f"Found {len(shows)} TV show results for '{query}'")
            xbmcplugin.addDirectoryItem(HANDLE, '', header, False)

            for meta in shows[:10]:
                item_id = meta.get('id')
                url = get_url(action='show_seasons', meta_id=item_id)
                list_item = create_listitem_with_context(meta, 'series', url)
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

            if len(shows) > 10:
                list_item = xbmcgui.ListItem(label=f'[COLOR yellow]   » View All TV Shows ({len(shows)} results)[/COLOR]')
                url = get_url(action='search_tab', content_type='series', query=query)
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    # No results handling
    if (not movie_results or not movie_results.get('metas')) and (not series_results or not series_results.get('metas')):
        list_item = xbmcgui.ListItem(label=f'[COLOR red]No results found for "{query}"[/COLOR]')
        xbmcplugin.addDirectoryItem(HANDLE, '', list_item, False)

    xbmcplugin.endOfDirectory(HANDLE)


def search_unified():
    """Wrapper for unified search action."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    query = params.get('query', '').strip()
    
    if not query:
        keyboard = xbmcgui.Dialog().input('Search', type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return
        query = keyboard.strip()
    
    # Use the shared unified results function
    search_all_results(query)




def play(params=None):
    """Play content - behavior depends on settings (show streams or auto-play first)."""

    # Close any existing DialogBusy without forcing it to stay closed
    # This prevents it from appearing but doesn't interfere with other dialogs
    xbmc.executebuiltin("Dialog.Close(busydialog)")

    if not params:
        params = dict(parse_qsl(sys.argv[2][1:]))

    content_type = params.get('content_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    # Extract metadata for stream dialog
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    clearlogo = params.get('clearlogo', '')


    # Format media ID for AIOStreams API
    if content_type == 'movie':
        media_id = imdb_id
        season = None
        episode = None
        title = params.get('title', 'Unknown')
    else:
        season = params.get('season')
        episode = params.get('episode')
        media_id = f"{imdb_id}:{season}:{episode}"
        title = params.get('title', f'S{season}E{episode}')

    # If metadata not provided in params, fetch it from API
    if not poster or not fanart or not clearlogo:
        xbmc.log(f'[AIOStreams] play() fetching metadata for {imdb_id} (poster={bool(poster)}, fanart={bool(fanart)}, clearlogo={bool(clearlogo)})', xbmc.LOGINFO)
        meta_data = get_meta(content_type, imdb_id)
        if meta_data and 'meta' in meta_data:
            meta = meta_data['meta']
            if not poster:
                poster = meta.get('poster', '')
            if not fanart:
                fanart = meta.get('background', '')
            if not clearlogo:
                clearlogo = meta.get('logo', '')

    # Show progress dialog while scraping streams
    # Calling setResolvedUrl(False) would cause a "Playback Failed" notification
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Scraping streams...')
    progress.update(0)

    try:
        # Fetch streams
        progress.update(25, 'Scraping streams...')
        stream_data = get_streams(content_type, media_id)
        progress.update(75)

        if not stream_data or 'streams' not in stream_data or len(stream_data['streams']) == 0:
            progress.close()
            xbmcgui.Dialog().notification('AIOStreams', 'No streams available', xbmcgui.NOTIFICATION_ERROR)
            return

        # Check default_behavior setting
        default_behavior = get_setting('default_behavior', 'show_streams')

        # Check if forced auto-play (e.g. from UpNext or Play First)
        # Check for explicit force_autoplay flag or specific actions
        action = params.get('action', '')
        force_autoplay = (params.get('force_autoplay') == 'true' or 
                         action in ['play_next', 'play_next_source', 'play_first'])

        # If set to show streams, show dialog instead of auto-playing
        # BUT only if not forced to auto-play
        if default_behavior == 'show_streams' and not force_autoplay:
            progress.update(100)
            progress.close()
            # Small delay to allow Kodi to fully clean up progress dialog before showing modal
            # Without this, Kodi may refuse to activate the stream selection dialog with error:
            # "Activate of window refused because there are active modal dialogs"
            xbmc.sleep(200)
            # Explicitly close any Kodi busy dialog that may be active
            xbmc.executebuiltin("Dialog.Close(busydialog)")
            xbmc.sleep(100)  # Brief delay to ensure busydialog is fully closed
            show_streams_dialog(content_type, media_id, stream_data, title, poster, fanart, clearlogo, from_playable=True)
            return

        # Otherwise, auto-play first stream
        progress.update(85, 'Preparing playback...')
        stream = stream_data['streams'][0]
        stream_url = stream.get('url') or stream.get('externalUrl')

        if not stream_url:
            progress.close()
            xbmc.sleep(500)  # Wait for dialog to close
            xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Create list item for playback
        list_item = xbmcgui.ListItem(path=stream_url)
        list_item.setProperty('IsPlayable', 'true')

        # Add subtitles if available
        progress.update(90, 'Loading subtitles...')
        subtitle_data = get_subtitles(content_type, media_id)
        if subtitle_data and 'subtitles' in subtitle_data:
            # Filter subtitles by user's language preferences
            filtered_subtitles = filter_subtitles_by_language(subtitle_data['subtitles'])

            subtitle_paths = []
            for subtitle in filtered_subtitles:
                sub_url = subtitle.get('url')
                if sub_url:
                    # Download subtitle with language-coded filename for proper Kodi display
                    lang = subtitle.get('lang', 'unknown')
                    sub_id = subtitle.get('id')
                    sub_path = download_subtitle_with_language(sub_url, lang, media_id, sub_id)
                    subtitle_paths.append(sub_path)
                    xbmc.log(f'[AIOStreams] Added subtitle [{lang}]: {sub_path}', xbmc.LOGINFO)

            if subtitle_paths:
                list_item.setSubtitles(subtitle_paths)

        # Set media info for scrobbling
        if HAS_MODULES and get_player():
            scrobble_type = 'movie' if content_type == 'movie' else 'episode'
            final_imdb_id = imdb_id
            
            # For episodes, fetch episode-specific IMDB ID from database
            if scrobble_type == 'episode' and season and episode:
                try:
                    from resources.lib.database.trakt_sync import TraktSyncDatabase
                    db = TraktSyncDatabase()
                    show_info = db.fetchone("SELECT trakt_id FROM shows WHERE imdb_id=?", (imdb_id,))
                    if show_info:
                        episode_info = db.fetchone(
                            "SELECT imdb_id FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                            (show_info['trakt_id'], int(season), int(episode))
                        )
                        if episode_info and episode_info['imdb_id']:
                            final_imdb_id = episode_info['imdb_id']
                            xbmc.log(f'[AIOStreams] Scrobbling with episode IMDB ID: {final_imdb_id}', xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f'[AIOStreams] Error fetching episode IMDB: {e}', xbmc.LOGWARNING)
            
            get_player().set_media_info(scrobble_type, final_imdb_id, season, episode)

        # Close progress and start playback
        progress.update(100, 'Starting playback...')
        progress.close()
        xbmc.sleep(500)  # Wait for dialog to close

        # Save stream list for auto-skip functionality
        try:
            # We save the list and the current index (0)
            # Filter stream list to minimal data to save memory/complexity
            min_streams = []
            for s in stream_data['streams']:
                # Save URL, title/name/info needed for playback
                min_streams.append({
                    'url': s.get('url') or s.get('externalUrl'),
                    'title': s.get('title', ''),
                    'source': s.get('source', '') 
                })
            
            window = xbmcgui.Window(10000)
            window.setProperty('AIOStreams.StreamList', json.dumps(min_streams))
            window.setProperty('AIOStreams.StreamIndex', '0')
            window.setProperty('AIOStreams.StreamMetadata', json.dumps({
                'content_type': content_type,
                'imdb_id': imdb_id,
                'season': season,
                'episode': episode,
                'title': title,
                'poster': poster,
                'fanart': fanart,
                'clearlogo': clearlogo
            }))
            xbmc.log(f'[AIOStreams] Saved {len(min_streams)} streams for auto-skip', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to save stream list: {e}', xbmc.LOGWARNING)

        # Decide how to play:
        # If we have a valid HANDLE (called as a plugin source), we MUST use setResolvedUrl.
        # If we don't (called via RunScript or similar), we use xbmc.Player().play().
        if HANDLE >= 0:
            xbmc.log(f'[AIOStreams] Resolving URL for playback (HANDLE={HANDLE}): {stream_url}', xbmc.LOGINFO)
            list_item.setPath(stream_url)
            xbmcplugin.setResolvedUrl(HANDLE, True, list_item)
            
            # When using setResolvedUrl, Kodi's internal player handles playback
            # We need to manually trigger our monitoring since callbacks won't fire on PLAYER
            # Use a small delay to let playback start, then call onPlayBackStarted manually
            def trigger_monitoring():
                xbmc.sleep(1000)  # Wait 1 second for playback to start
                if xbmc.Player().isPlaying():
                    get_player().onPlayBackStarted()
            
            import threading
            threading.Thread(target=trigger_monitoring, daemon=True).start()
        else:
            xbmc.log(f'[AIOStreams] Initiating Player (HANDLE={HANDLE}): {stream_url}', xbmc.LOGINFO)
            get_player().play(stream_url, list_item)

    except Exception as e:
        progress.close()
        xbmc.log(f'[AIOStreams] Play error: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', f'Playback error: {str(e)}', xbmcgui.NOTIFICATION_ERROR)


def play_first():
    """Play first stream directly - ignores default_behavior setting (for TMDBHelper)."""
    # Close any existing DialogBusy without forcing it to stay closed
    # This prevents it from appearing but doesn't interfere with other dialogs
    xbmc.executebuiltin("Dialog.Close(busydialog)")

    # IMPORTANT: Cancel resolver state immediately if called from resolvable context
    # This prevents "failed to play item" errors when using xbmc.Player().play() directly
    # We do this BEFORE any blocking operations to avoid Kodi waiting on resolver
    if HANDLE >= 0:
        try:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        except:
            pass  # Not in a resolvable context, ignore

    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params['content_type']
    imdb_id = params['imdb_id']

    # Format media ID for AIOStreams API
    if content_type == 'movie':
        media_id = imdb_id
        season = None
        episode = None
    else:
        season = params.get('season')
        episode = params.get('episode')
        media_id = f"{imdb_id}:{season}:{episode}"

    # Show progress dialog while scraping streams
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Scraping streams...')
    progress.update(0)

    try:
        # Fetch streams
        progress.update(25, 'Scraping streams...')
        stream_data = get_streams(content_type, media_id)
        progress.update(75)

        if not stream_data or 'streams' not in stream_data or len(stream_data['streams']) == 0:
            progress.close()
            xbmcgui.Dialog().notification('AIOStreams', 'No streams available', xbmcgui.NOTIFICATION_ERROR)
            return

        # Always auto-play first stream (ignore default_behavior setting)
        progress.update(85, 'Preparing playback...')
        stream = stream_data['streams'][0]
        stream_url = stream.get('url') or stream.get('externalUrl')

        if not stream_url:
            progress.close()
            xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Create list item for playback
        list_item = xbmcgui.ListItem(path=stream_url)
        list_item.setProperty('IsPlayable', 'true')

        # Add subtitles if available
        progress.update(90, 'Loading subtitles...')
        subtitle_data = get_subtitles(content_type, media_id)
        if subtitle_data and 'subtitles' in subtitle_data:
            # Filter subtitles by user's language preferences
            filtered_subtitles = filter_subtitles_by_language(subtitle_data['subtitles'])

            subtitle_paths = []
            for subtitle in filtered_subtitles:
                sub_url = subtitle.get('url')
                if sub_url:
                    # Download subtitle with language-coded filename for proper Kodi display
                    lang = subtitle.get('lang', 'unknown')
                    sub_id = subtitle.get('id')
                    sub_path = download_subtitle_with_language(sub_url, lang, media_id, sub_id)
                    subtitle_paths.append(sub_path)
                    xbmc.log(f'[AIOStreams] Added subtitle [{lang}]: {sub_path}', xbmc.LOGINFO)

            if subtitle_paths:
                list_item.setSubtitles(subtitle_paths)

        # Set media info for scrobbling
        if HAS_MODULES and get_player():
            scrobble_type = 'movie' if content_type == 'movie' else 'episode'
            final_imdb_id = imdb_id
            
            # For episodes, fetch episode-specific IMDB ID from database
            if scrobble_type == 'episode' and season and episode:
                try:
                    from resources.lib.database.trakt_sync import TraktSyncDatabase
                    db = TraktSyncDatabase()
                    show_info = db.fetchone("SELECT trakt_id FROM shows WHERE imdb_id=?", (imdb_id,))
                    if show_info:
                        episode_info = db.fetchone(
                            "SELECT imdb_id FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                            (show_info['trakt_id'], int(season), int(episode))
                        )
                        if episode_info and episode_info['imdb_id']:
                            final_imdb_id = episode_info['imdb_id']
                            xbmc.log(f'[AIOStreams] Scrobbling with episode IMDB ID: {final_imdb_id}', xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f'[AIOStreams] Error fetching episode IMDB: {e}', xbmc.LOGWARNING)
            
            get_player().set_media_info(scrobble_type, final_imdb_id, season, episode)

        # Close progress and start playback
        progress.update(100, 'Starting playback...')
        progress.close()

        # Use xbmc.Player().play() for direct playback
        xbmc.Player().play(stream_url, list_item)

    except Exception as e:
        progress.close()
        xbmc.log(f'[AIOStreams] Play first error: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', f'Playback error: {str(e)}', xbmcgui.NOTIFICATION_ERROR)


def format_stream_title(stream, for_dialog=False):
    """
    Format stream title for display.

    Args:
        stream: Stream data dictionary
        for_dialog: If True, format for Dialog().select() (plain text, no color codes)
                    If False, format for ListItems (with color codes)

    Expected format: SERVICE|QUALITY|SIZE|SOURCE|CACHED_STATUS
    Example: RD|4K|10.27 GB|StremThru Torz|Cached
    """
    stream_name = stream.get('name', stream.get('title', ''))
    description = stream.get('description', '')

    # Try to parse the formatted stream name
    try:
        parts = stream_name.split('|')
        if len(parts) >= 4:
            service = parts[0].strip()
            quality = parts[1].strip()
            size = parts[2].strip()
            source = parts[3].strip()
            cached_status = parts[4].strip() if len(parts) > 4 else ''

            if for_dialog:
                # Plain text formatting for Dialog().select()
                # Use symbols for visual appeal: ✓ for cached, ⏳ for uncached, ★ for 4K
                quality_symbol = '★ ' if '4K' in quality or '2160' in quality else ''

                # Cached status symbol
                if 'cached' in cached_status.lower():
                    cached_symbol = '✓'
                elif 'uncached' in cached_status.lower():
                    cached_symbol = '⏳'
                else:
                    cached_symbol = '?'

                # Format: [SERVICE] Quality • Size • Source • Status
                formatted = f'[{service}] {quality_symbol}{quality} • {size} • {source} {cached_symbol}'
            else:
                # Color-coded formatting for ListItems
                if service == 'RD':
                    service_colored = f'[COLOR green][{service}][/COLOR]'
                elif service == 'TB':
                    service_colored = f'[COLOR yellow][{service}][/COLOR]'
                elif service:
                    service_colored = f'[COLOR blue][{service}][/COLOR]'
                else:
                    service_colored = ''

                quality_tag = f'[{quality}] ' if quality else ''
                size_text = f'{size} ' if size else ''
                source_text = f'{source} ' if source else ''

                if 'cached' in cached_status.lower():
                    cached_icon = '✓'
                elif 'uncached' in cached_status.lower():
                    cached_icon = '⏳'
                else:
                    cached_icon = ''

                formatted = f'{quality_tag}{size_text}{source_text}{cached_icon} {service_colored}'.strip()

            # Append description if available (only for ListItems)
            if description and not for_dialog:
                formatted = f'{formatted}\n[COLOR gray]{description}[/COLOR]'

            return formatted
        else:
            # Format doesn't match expected pattern, return original
            return stream_name
    except Exception as e:
        # On any error, return the original stream name
        xbmc.log(f'[AIOStreams] Error formatting stream title: {e}', xbmc.LOGDEBUG)
        return stream_name


def select_stream():
    """TMDBHelper select stream - show dialog to select from available streams."""
    # Close any existing DialogBusy without forcing it to stay closed
    # This prevents it from appearing but doesn't interfere with other dialogs
    xbmc.executebuiltin("Dialog.Close(busydialog)")

    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params['content_type']
    imdb_id = params['imdb_id']
    title = params.get('title', '')
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    clearlogo = params.get('clearlogo', '')

    # Format media ID for AIOStreams API
    if content_type == 'movie':
        media_id = imdb_id
        season = None
        episode = None
    else:
        season = params.get('season')
        episode = params.get('episode')
        media_id = f"{imdb_id}:{season}:{episode}"

    # Cancel Kodi's resolver state immediately to avoid modal dialog conflicts
    # TMDBHelper calls this as a resolver, but we need to show a dialog first
    # MUST be done before any API calls or dialog shows
    xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())

    # Show progress dialog immediately to replace Kodi's error notification
    # This prevents modal dialog conflicts
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Fetching metadata...')
    progress.update(0)

    try:
        # If metadata not provided in params (common with TMDBHelper), fetch it from API
        if not poster or not fanart or not clearlogo:
            xbmc.log(f'[AIOStreams] select_stream() fetching metadata for {imdb_id} (poster={bool(poster)}, fanart={bool(fanart)}, clearlogo={bool(clearlogo)})', xbmc.LOGINFO)
            meta_data = get_meta(content_type, imdb_id)
            if meta_data and 'meta' in meta_data:
                meta = meta_data['meta']
                if not poster:
                    poster = meta.get('poster', '')
                if not fanart:
                    fanart = meta.get('background', '')
                if not clearlogo:
                    clearlogo = meta.get('logo', '')
                if not title:
                    title = meta.get('name', '')
                plot = meta.get('description', '')
            else:
                plot = ''
        else:
            plot = params.get('plot', '')
        
        if not plot:
            plot = xbmc.getInfoLabel('ListItem.Plot')

        # Update progress for stream fetching
        progress.update(50, 'Scraping streams...')

        # Fetch streams
        stream_data = get_streams(content_type, media_id)
    finally:
        progress.close()

    # Small delay to allow Kodi to fully clean up progress dialog before showing modal
    # Without this, Kodi may refuse to activate the stream selection dialog with error:
    # "Activate of window refused because there are active modal dialogs"
    xbmc.sleep(200)

    if not stream_data or 'streams' not in stream_data or len(stream_data['streams']) == 0:
        xbmcgui.Dialog().notification('AIOStreams', 'No streams available', xbmcgui.NOTIFICATION_ERROR)
        return

    # Use stream manager for enhanced display (same as show_streams_dialog)
    if HAS_MODULES:
        stream_mgr = streams.get_stream_manager()

        # Filter streams by quality
        filtered_streams = stream_mgr.filter_by_quality(stream_data['streams'])

        # Sort streams by reliability and quality
        sorted_streams = stream_mgr.sort_streams(filtered_streams)

        # Limit number of streams
        max_streams = settings_helpers.get_max_streams()
        sorted_streams = sorted_streams[:max_streams]

        # Update stream_data with sorted streams
        stream_data['streams'] = sorted_streams

    # Check if we have any streams after filtering
    if not stream_data['streams']:
        xbmcgui.Dialog().notification('AIOStreams', 'No streams match your quality preferences', xbmcgui.NOTIFICATION_ERROR)
        return

    # Use custom multi-line dialog with emoji support
    xbmc.log(f'[AIOStreams] Showing stream selection dialog with {len(stream_data["streams"])} streams', xbmc.LOGDEBUG)

    # Explicitly close any Kodi busy dialog that may be active
    xbmc.executebuiltin("Dialog.Close(busydialog)")
    xbmc.sleep(100)  # Brief delay to ensure busydialog is fully closed

    # Use custom dialog if available
    if HAS_MODULES:
        try:
            selected, selected_stream = show_source_select_dialog(
                streams=stream_data['streams'],
                title=title if title else 'Select Stream',
                fanart=fanart,
                poster=poster,
                clearlogo=clearlogo,
                plot=plot
            )
            xbmc.log(f'[AIOStreams] Custom dialog returned: selected={selected}', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Custom dialog failed, falling back: {e}', xbmc.LOGERROR)
            selected = -1
    else:
        selected = -1

    # Fallback to standard dialog if custom dialog not available or failed
    if selected == -1 and not HAS_MODULES:
        stream_list = []
        for stream in stream_data['streams']:
            stream_name = stream.get('name', 'Unknown Stream')
            stream_desc = stream.get('description', '')
            full_label = f"{stream_name} {stream_desc}" if stream_desc else stream_name
            list_item = xbmcgui.ListItem(label=full_label)
            stream_list.append(list_item)

        selected = xbmcgui.Dialog().select(
            f"Select Stream ({len(stream_list)} available)",
            stream_list,
            useDetails=False
        )

    if selected < 0:
        return

    # Record selection for learning
    if HAS_MODULES:
        stream_mgr.record_stream_selection(stream_data['streams'][selected].get('name', ''))

    # Get selected stream
    stream = stream_data['streams'][selected]
    stream_url = stream.get('url') or stream.get('externalUrl')

    if not stream_url:
        xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
        return
    
    # Create list item for playback
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')
    
    # Add subtitles if available
    subtitle_data = get_subtitles(content_type, media_id)
    if subtitle_data and 'subtitles' in subtitle_data:
        # Filter subtitles by user's language preferences
        filtered_subtitles = filter_subtitles_by_language(subtitle_data['subtitles'])

        subtitle_paths = []
        for subtitle in filtered_subtitles:
            sub_url = subtitle.get('url')
            if sub_url:
                # Download subtitle with language-coded filename for proper Kodi display
                lang = subtitle.get('lang', 'unknown')
                sub_id = subtitle.get('id')
                sub_path = download_subtitle_with_language(sub_url, lang, media_id, sub_id)
                subtitle_paths.append(sub_path)
                xbmc.log(f'[AIOStreams] Added subtitle [{lang}]: {sub_path}', xbmc.LOGINFO)

        if subtitle_paths:
            list_item.setSubtitles(subtitle_paths)
    
    # Set media info for scrobbling
    if HAS_MODULES and get_player():
        scrobble_type = 'movie' if content_type == 'movie' else 'episode'
        get_player().set_media_info(scrobble_type, imdb_id, season, episode)

    # Use direct playback instead of setResolvedUrl to avoid modal dialog conflicts
    # When showing a selection dialog, setResolvedUrl can timeout waiting for resolution
    xbmc.Player().play(stream_url, list_item)


def movie_lists():
    """Movie lists submenu."""
    from resources.lib import trakt
    xbmcplugin.setPluginCategory(HANDLE, 'Movie Lists')
    xbmcplugin.setContent(HANDLE, 'videos')
    
    menu_items = [
        {'label': 'AIOStreams Catalogs', 'url': get_url(action='catalogs', content_type='movie'), 'icon': 'DefaultMovies.png'}
    ]

    # Add Trakt lists if authorized
    if HAS_MODULES and trakt.get_access_token():
        menu_items.extend([
            {'label': 'Watchlist - Trakt', 'url': get_url(action='trakt_watchlist', media_type='movies'), 'icon': 'DefaultMovies.png'}
        ])
    
    for item in menu_items:
        list_item = xbmcgui.ListItem(label=item['label'])
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(item['label'])
        list_item.setArt({'icon': item['icon']})
        xbmcplugin.addDirectoryItem(HANDLE, item['url'], list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def series_lists():
    """Series lists submenu."""
    from resources.lib import trakt
    xbmcplugin.setPluginCategory(HANDLE, 'Series Lists')
    xbmcplugin.setContent(HANDLE, 'videos')

    menu_items = [
        {'label': 'AIOStreams Catalogs', 'url': get_url(action='catalogs', content_type='series'), 'icon': 'DefaultTVShows.png'}
    ]

    # Add Trakt lists if authorized
    if HAS_MODULES and trakt.get_access_token():
        menu_items.extend([
            {'label': 'Next Up - Trakt', 'url': get_url(action='trakt_next_up'), 'icon': 'DefaultTVShows.png'},
            {'label': 'Watchlist - Trakt', 'url': get_url(action='trakt_watchlist', media_type='shows'), 'icon': 'DefaultTVShows.png'}
        ])
    
    for item in menu_items:
        list_item = xbmcgui.ListItem(label=item['label'])
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(item['label'])
        list_item.setArt({'icon': item['icon']})
        xbmcplugin.addDirectoryItem(HANDLE, item['url'], list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def list_catalogs():
    """List all available catalogs from manifest."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    filter_type = params.get('content_type')  # 'movie' or 'series'
    is_widget = params.get('widget') == 'true'
    
    manifest = get_manifest()

    if not manifest or 'catalogs' not in manifest:
        xbmcgui.Dialog().notification('AIOStreams', 'No catalogs available', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    category_name = 'Movie Catalogs' if filter_type == 'movie' else 'Series Catalogs' if filter_type == 'series' else 'All Catalogs'
    xbmcplugin.setPluginCategory(HANDLE, category_name)
    xbmcplugin.setContent(HANDLE, 'videos')
    
    for catalog in manifest['catalogs']:
        catalog_name = catalog.get('name', 'Unknown Catalog')
        catalog_id = catalog.get('id')
        content_type = catalog.get('type', 'movie')
        
        # Filter by type if specified
        if filter_type and content_type != filter_type:
            continue
        
        # Skip search catalogs - we have our own search function
        if 'search' in catalog_name.lower() or 'search' in catalog_id.lower():
            continue
        
        extras = catalog.get('extra', [])
        genre_extra = next((e for e in extras if e.get('name') == 'genre'), None)
        
        if not is_widget and genre_extra and genre_extra.get('options'):
            url = get_url(action='catalog_genres', catalog_id=catalog_id, content_type=content_type, catalog_name=catalog_name)
            is_folder = True
        elif is_widget and genre_extra and genre_extra.get('options'):
            # widget=true skips genre selection and goes to "All"
            url = get_url(action='browse_catalog', catalog_id=catalog_id, content_type=content_type, catalog_name=catalog_name, genre='All')
            is_folder = True
        else:
            url = get_url(action='browse_catalog', catalog_id=catalog_id, content_type=content_type, catalog_name=catalog_name)
            is_folder = True
        
        list_item = xbmcgui.ListItem(label=catalog_name)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(catalog_name)
        icon = 'DefaultMovies.png' if content_type == 'movie' else 'DefaultTVShows.png'
        list_item.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)
    
    xbmcplugin.endOfDirectory(HANDLE)


def list_catalog_genres():
    """List genre options for a catalog."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    catalog_id = params['catalog_id']
    content_type = params['content_type']
    catalog_name = params.get('catalog_name', 'Catalog')
    
    manifest = get_manifest()
    if not manifest:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    catalog = next((c for c in manifest['catalogs'] if c['id'] == catalog_id and c['type'] == content_type), None)
    if not catalog:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    xbmcplugin.setPluginCategory(HANDLE, catalog_name)
    xbmcplugin.setContent(HANDLE, 'videos')
    
    # Add "All" option
    list_item = xbmcgui.ListItem(label='All')
    info_tag = list_item.getVideoInfoTag()
    info_tag.setTitle('All')
    url = get_url(action='browse_catalog', catalog_id=catalog_id, content_type=content_type, catalog_name=catalog_name, genre='All')
    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    # Add genre options
    extras = catalog.get('extra', [])
    genre_extra = next((e for e in extras if e.get('name') == 'genre'), None)

    if genre_extra and genre_extra.get('options'):
        for genre in genre_extra['options']:
            list_item = xbmcgui.ListItem(label=genre)
            info_tag = list_item.getVideoInfoTag()
            info_tag.setTitle(genre)
            url = get_url(action='browse_catalog', catalog_id=catalog_id, content_type=content_type, catalog_name=catalog_name, genre=genre)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)

def browse_catalog():
    """Browse a specific catalog with optional genre filter."""
    from resources.lib import trakt
    xbmcgui.Window(10000).clearProperty('AIOStreams_ShowLogo')
    params = dict(parse_qsl(sys.argv[2][1:]))
    catalog_id = params['catalog_id']
    content_type = params['content_type']
    catalog_name = params.get('catalog_name', 'Catalog')
    genre = params.get('genre')
    skip = int(params.get('skip', 0))

    # Prime watchlist and watched caches for performance (batch fetch)
    if HAS_MODULES:
        trakt.prime_database_cache(content_type)
        
    # Fetch catalog data (treat 'All' as no genre filter)
    genre_filter = None if genre == 'All' else genre
    catalog_data = get_catalog(content_type, catalog_id, genre_filter, skip)

    if not catalog_data or 'metas' not in catalog_data:
        xbmcgui.Dialog().notification('AIOStreams', 'No items found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Apply filters
    if HAS_MODULES and filters:
        catalog_data['metas'] = filters.filter_items(catalog_data['metas'])

    # Build category name: "Catalog Name > Genre" or just "Catalog Name"
    if genre and genre != 'All':
        category_title = f'{catalog_name} > {genre}'
    else:
        category_title = catalog_name

    xbmcplugin.setPluginCategory(HANDLE, category_title)
    xbmcplugin.setContent(HANDLE, 'movies' if content_type == 'movie' else 'tvshows')
    
    # Display catalog items
    for meta in catalog_data['metas']:
        item_id = meta.get('id')
        item_type = meta.get('type', content_type)
        
        # Determine if this is a series or movie
        if item_type == 'series':
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        else:
            title = meta.get('name', 'Unknown')
            poster = meta.get('poster', '')
            fanart = meta.get('background', '')
            clearlogo = meta.get('logo', '')
            url = get_url(action='play', content_type='movie', imdb_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)
    
    # Check if next page exists by checking metas count
    # If we got a full page (20 items), assume there might be more
    if len(catalog_data['metas']) >= 20:
        next_skip = skip + 20
        # Show "More Results" with image
        list_item = xbmcgui.ListItem(label='More Results')
        list_item.setArt({'thumb': 'special://skin/media/more.png', 'poster': 'special://skin/media/more.png'})
        url = get_url(action='browse_catalog', catalog_id=catalog_id, content_type=content_type,
                      catalog_name=catalog_name, genre=genre if genre else '', skip=next_skip)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    # Set NumItems property if called from smart_widget
    if params.get("page") and params.get("index"):
        count_prop = f"AIOStreams.{params['page']}.{params['index']}.NumItems"
        item_count = len(catalog_data["metas"])
        xbmcgui.Window(10000).setProperty(count_prop, str(item_count))
        xbmc.log(f"[AIOStreams] Set {count_prop} = {item_count}", xbmc.LOGDEBUG)

    xbmcplugin.endOfDirectory(HANDLE)


def show_streams():
    """Show streams for a catalog item in a dialog window."""
    from resources.lib import trakt
    xbmcgui.Window(10000).clearProperty('AIOStreams_ShowLogo')
    # Close any existing DialogBusy without forcing it to stay closed
    # This prevents it from appearing but doesn't interfere with other dialogs
    xbmc.executebuiltin("Dialog.Close(busydialog)")

    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params['content_type']
    media_id = params['media_id']
    title = params.get('title', 'Unknown')
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    clearlogo = params.get('clearlogo', '')
    plot = params.get('plot', '')


    # Show loading dialog while fetching streams
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Scraping streams...')

    try:
        # Fetch streams
        stream_data = get_streams(content_type, media_id)
    finally:
        progress.close()

    if not stream_data or 'streams' not in stream_data or len(stream_data['streams']) == 0:
        xbmcgui.Dialog().notification('AIOStreams', 'No streams available', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # Small delay to allow Kodi to fully clean up progress dialog before showing modal
    # Without this, Kodi may refuse to activate the stream selection dialog with error:
    # "Activate of window refused because there are active modal dialogs"
    xbmc.sleep(200)
    # Explicitly close any Kodi busy dialog that may be active
    xbmc.executebuiltin("Dialog.Close(busydialog)")
    xbmc.sleep(100)  # Brief delay to ensure busydialog is fully closed

    # Always show streams dialog (ignore default behavior - user explicitly requested stream selection)
    show_streams_dialog(content_type, media_id, stream_data, title, poster, fanart, clearlogo, plot=plot)


def show_streams_dialog(content_type, media_id, stream_data, title, poster='', fanart='', clearlogo='', from_playable=False, plot=''):
    """Show streams in a selection dialog.

    Args:
        from_playable: If True, called from playable listitem context (don't use endOfDirectory)
    """

    if not HAS_MODULES:
        # Fallback to simple dialog - use custom formatting
        stream_list = []
        for stream in stream_data['streams']:
            formatted_title = format_stream_title(stream)
            stream_list.append(formatted_title)
    else:
        # Use stream manager for enhanced display
        stream_mgr = streams.get_stream_manager()

        # Filter streams by quality
        filtered_streams = stream_mgr.filter_by_quality(stream_data['streams'])

        # Sort streams by reliability and quality
        sorted_streams = stream_mgr.sort_streams(filtered_streams)

        # Limit number of streams
        max_streams = settings_helpers.get_max_streams()
        sorted_streams = sorted_streams[:max_streams]

        # Update stream_data with sorted streams
        stream_data['streams'] = sorted_streams

    # Check if we have any streams
    if not stream_data['streams']:
        xbmcgui.Dialog().notification('AIOStreams', 'No streams match your quality preferences', xbmcgui.NOTIFICATION_ERROR)
        if not from_playable:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # Use custom multi-line dialog with emoji support
    xbmc.log(f'[AIOStreams] Showing stream selection dialog with {len(stream_data["streams"])} streams', xbmc.LOGDEBUG)

    # Explicitly close any Kodi busy dialog that may be active
    xbmc.executebuiltin("Dialog.Close(busydialog)")
    xbmc.sleep(100)  # Brief delay to ensure busydialog is fully closed

    # Use custom dialog if available
    if HAS_MODULES:
        try:
            selected, selected_stream = show_source_select_dialog(
                streams=stream_data['streams'],
                title=title if title else 'Select Stream',
                fanart=fanart,
                poster=poster,
                clearlogo=clearlogo,
                plot=plot
            )
            xbmc.log(f'[AIOStreams] Custom dialog returned: selected={selected}', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Custom dialog failed, falling back: {e}', xbmc.LOGERROR)
            selected = -1
    else:
        selected = -1

    # Fallback to standard dialog if custom dialog not available or failed
    if selected == -1 and not HAS_MODULES:
        stream_list = []
        for stream in stream_data['streams']:
            stream_name = stream.get('name', 'Unknown Stream')
            stream_desc = stream.get('description', '')
            full_label = f"{stream_name} {stream_desc}" if stream_desc else stream_name
            list_item = xbmcgui.ListItem(label=full_label)
            stream_list.append(list_item)

        selected = xbmcgui.Dialog().select(
            f"Select Stream ({len(stream_list)} available)",
            stream_list,
            useDetails=False
        )

    if selected < 0:
        # User cancelled - don't call endOfDirectory if from playable context
        if not from_playable:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # Record selection for learning
    if HAS_MODULES:
        stream_mgr.record_stream_selection(stream_data['streams'][selected].get('name', ''))

    # Play selected stream
    # Use resolved playback if from_playable is True (Kodi waiting for resolution)
    # Use direct playback if from_playable is False (RunPlugin context)
    use_player_actual = not from_playable
    if not play_stream_by_index(content_type, media_id, stream_data, selected, use_player=use_player_actual):
        # Playback failed, try next streams
        xbmc.log('[AIOStreams] Selected stream failed, trying next available...', xbmc.LOGINFO)
        try_next_streams(content_type, media_id, stream_data, start_index=selected+1, use_player=use_player_actual)


def play_stream_by_index(content_type, media_id, stream_data, index, use_player=False):
    """Play a stream by its index in the stream list.

    Args:
        content_type: Type of content ('movie' or 'series')
        media_id: Media ID (IMDB for movies, imdb:season:episode for series)
        stream_data: Stream data dict with 'streams' list
        index: Index of stream to play
        use_player: If True, use xbmc.Player().play() (for RunPlugin context)
                    If False, use setResolvedUrl (for playable listitem context)
    """
    if index >= len(stream_data['streams']):
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid stream index', xbmcgui.NOTIFICATION_ERROR)
        if not use_player:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return False

    stream = stream_data['streams'][index]
    stream_url = stream.get('url') or stream.get('externalUrl')

    if not stream_url:
        xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
        if not use_player:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return False

    # Create list item for playback
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')

    # Add subtitles if available
    subtitle_data = get_subtitles(content_type, media_id)
    if subtitle_data and 'subtitles' in subtitle_data:
        # Filter subtitles by user's language preferences
        filtered_subtitles = filter_subtitles_by_language(subtitle_data['subtitles'])

        subtitle_paths = []
        for subtitle in filtered_subtitles:
            sub_url = subtitle.get('url')
            if sub_url:
                # Download subtitle with language-coded filename for proper Kodi display
                lang = subtitle.get('lang', 'unknown')
                sub_id = subtitle.get('id')
                sub_path = download_subtitle_with_language(sub_url, lang, media_id, sub_id)
                subtitle_paths.append(sub_path)
                xbmc.log(f'[AIOStreams] Added subtitle [{lang}]: {sub_path}', xbmc.LOGINFO)

        if subtitle_paths:
            list_item.setSubtitles(subtitle_paths)

    # Set media info for scrobbling
    if HAS_MODULES and get_player():
        # Parse media_id for episodes (format: show_imdb_id:season:episode)
        if content_type == 'series' and ':' in media_id:
            parts = media_id.split(':')
            show_imdb_id = parts[0]
            season = parts[1] if len(parts) > 1 else None
            episode = parts[2] if len(parts) > 2 else None
            
            # CRITICAL FIX: Fetch episode IMDB ID from database instead of using show IMDB ID
            episode_imdb_id = show_imdb_id  # Fallback to show ID
            try:
                from resources.lib.database.trakt_sync import TraktSyncDatabase
                db = TraktSyncDatabase()
                show_info = db.fetchone("SELECT trakt_id FROM shows WHERE imdb_id=?", (show_imdb_id,))
                
                if show_info and season and episode:
                    episode_info = db.fetchone(
                        "SELECT imdb_id FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                        (show_info['trakt_id'], int(season), int(episode))
                    )
                    
                    if episode_info and episode_info['imdb_id']:
                        episode_imdb_id = episode_info['imdb_id']
            except Exception as e:
                pass
            
            get_player().set_media_info('episode', episode_imdb_id, season, episode)
            
            get_player().set_media_info('episode', episode_imdb_id, season, episode)
        else:
            get_player().set_media_info('movie', media_id, None, None)

    # Start playback using appropriate method
    if use_player:
        # Called from RunPlugin context (e.g., "Scrape Streams" context menu)
        # Use direct playback
        xbmc.log(f'[AIOStreams] Starting direct playback: {stream_url}', xbmc.LOGINFO)
        player = xbmc.Player()
        player.play(stream_url, list_item)
    else:
        # Called from playable listitem context (e.g., clicking a movie/episode)
        # Use setResolvedUrl
        xbmcplugin.setResolvedUrl(HANDLE, True, list_item)

    # Monitor playback with 30 second timeout
    playback_started = False
    monitor = xbmc.Monitor()
    player = xbmc.Player()

    # Wait up to 30 seconds for playback to start
    for i in range(300):  # 300 * 0.1 = 30 seconds
        if monitor.abortRequested():
            return False
        if player.isPlaying():
            playback_started = True
            break
        monitor.waitForAbort(0.1)

    # Record stream attempt
    if HAS_MODULES:
        stream_mgr = streams.get_stream_manager()
        stream_mgr.record_stream_result(stream_url, playback_started)

    # If playback didn't start within 30 seconds, handle fallback
    if not playback_started:
        xbmc.log('[AIOStreams] Stream playback timeout after 30 seconds', xbmc.LOGWARNING)
        # Return False to trigger fallback behavior
        return False

    # Check runtime duration to filter out short/broken streams
    if use_player and playback_started:
        total_time = player.getTotalTime()
        if total_time > 0 and total_time < 95:
            xbmc.log(f'[AIOStreams] Stream duration too short ({total_time}s), skipping...', xbmc.LOGWARNING)
            player.stop()
            if HAS_MODULES:
                stream_mgr = streams.get_stream_manager()
                stream_mgr.record_stream_result(stream_url, False) # Mark as failure
            return False

    return True


def try_next_streams(content_type, media_id, stream_data, start_index=1, use_player=False):
    """Try to play streams sequentially starting from start_index."""
    for i in range(start_index, len(stream_data['streams'])):
        # Check for abort before playing next
        if xbmc.Monitor().abortRequested():
            return

        xbmc.log(f'[AIOStreams] Auto-trying stream index {i}', xbmc.LOGINFO)
        success = play_stream_by_index(content_type, media_id, stream_data, i, use_player=use_player)
        if success:
            return

    # All streams failed
    xbmcgui.Dialog().notification('AIOStreams', 'All streams failed', xbmcgui.NOTIFICATION_ERROR)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def show_seasons():
    """Show seasons for a TV series."""
    from resources.lib import trakt
    params = dict(parse_qsl(sys.argv[2][1:]))
    meta_id = params['meta_id']
    
    # === DB OPTIMIZATION: Try local SyncDB first ===
    meta_data = None
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        db = TraktSyncDatabase()
        
        # Resolve Trakt ID if needed
        trakt_id = None
        if isinstance(meta_id, int) or (isinstance(meta_id, str) and meta_id.isdigit()):
            trakt_id = int(meta_id)
        elif isinstance(meta_id, str) and meta_id.startswith('tt'):
            trakt_id = db.get_trakt_id_for_item(meta_id, 'show')
            
        if trakt_id:
            # Try to get show data from local DB
            show_row = db.get_show(trakt_id)
            if show_row and show_row.get('metadata'):
                show_meta = show_row['metadata']
                # Try to get episodes from local DB
                episode_rows = db.get_episodes_for_show(trakt_id)
                if episode_rows:
                    videos = []
                    for row in episode_rows:
                        ep_data = row.get('metadata', {}) or {}
                        # Ensure minimal keys
                        if 'season' not in ep_data: ep_data['season'] = row['season']
                        if 'episode' not in ep_data: ep_data['episode'] = row['episode']
                        videos.append(ep_data)
                    
                    show_meta['videos'] = videos
                    # Construct the 'meta_data' structure expected below
                    meta_data = {'meta': show_meta}
                    xbmc.log(f'[AIOStreams] Loaded {len(videos)} episodes from local SyncDB', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] SyncDB optimization error: {e}', xbmc.LOGERROR)

    if not meta_data:
        meta_data = get_meta('series', meta_id)
    
    if not meta_data or 'meta' not in meta_data:
        xbmcgui.Dialog().notification('AIOStreams', 'Series info not found', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    meta = meta_data['meta']
    series_name = meta.get('name', 'Unknown Series')
    
    xbmcplugin.setPluginCategory(HANDLE, series_name)
    xbmcplugin.setContent(HANDLE, 'seasons')
    
    videos = meta.get('videos', [])
    
    # Set window-level artwork properties for the skin
    logo_url = meta.get('logo')
    if logo_url:
        cached_logo = get_cached_clearlogo_path('series', meta_id)
        win = xbmcgui.Window(10000)
        win.setProperty('AIOStreams_ShowLogo', cached_logo or logo_url)
        win.setProperty('AIOStreams_HasLogo', 'true')
        if not cached_logo:
             _ensure_clearlogo_cached(meta, 'series', meta_id)
    else:
        xbmcgui.Window(10000).setProperty('AIOStreams_HasLogo', 'false')
    
    if not videos:
        xbmcgui.Dialog().notification('AIOStreams', 'No seasons found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    # Group episodes by season
    seasons = {}
    for video in videos:
        season = video.get('season')
        if season is not None:
            if season not in seasons:
                seasons[season] = []
            seasons[season].append(video)

    # Get Trakt data once for all seasons (performance optimization)
    show_progress = None
    show_in_watchlist = False
    if HAS_MODULES and trakt.get_access_token():
        show_progress = trakt.get_show_progress(meta_id)
        show_in_watchlist = trakt.is_in_watchlist('series', meta_id)

    # Display seasons
    for season_num in sorted(seasons.keys()):
        episode_count = len(seasons[season_num])

        # Get season progress from cached show progress
        aired = 0
        completed = 0
        is_season_watched = False

        if show_progress:
            seasons_data = show_progress.get('seasons', [])
            for s in seasons_data:
                if s.get('number') == season_num:
                    aired = s.get('aired', 0)
                    completed = s.get('completed', 0)
                    is_season_watched = aired > 0 and aired == completed
                    break

        # Format season label with UI enhancements
        if HAS_MODULES:
            season_label = ui_helpers.format_season_title(season_num, episode_count, aired, completed)
        else:
            season_label = f'Season {season_num} ({episode_count} episodes)'

        list_item = xbmcgui.ListItem(label=season_label)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(season_label)
        info_tag.setSeason(season_num)
        info_tag.setTvShowTitle(series_name)
        info_tag.setMediaType('season')
        
        # Ensure plot is available (fallback to show plot)
        plot = meta.get('plot', '') or meta.get('overview', '')
        # Ensure plot is available (fallback to show plot)
        plot = meta.get('plot') or meta.get('overview') or meta.get('description', '')
        xbmc.log(f'[AIOStreams] Season {season_num}: Plot="{plot}"', xbmc.LOGINFO)
        if not plot:
             xbmc.log(f'[AIOStreams] Meta Keys Available: {list(meta.keys())}', xbmc.LOGINFO)
             plot = "DEBUG: Plot missing from metadata"
             
        info_tag.setPlot(plot)
        list_item.setProperty('Plot', plot)
        list_item.setProperty('TVShowPlot', plot)
        list_item.setProperty('Overview', plot)
        list_item.setProperty('DEBUG_PLOT', 'DEBUG_MODE_ON')
        
        # Set properties for safe update call
        list_item.setProperty('meta_id', str(meta_id))
        list_item.setProperty('season_num', str(season_num))

        # Set playcount if watched
        if is_season_watched:
            info_tag.setPlaycount(1)
            list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')

        logo_url = meta.get('logo')
        if logo_url:
            cached_logo = get_cached_clearlogo_path('series', meta_id)
            if cached_logo:
                list_item.setArt({'poster': meta.get('poster', ''), 'thumb': meta.get('poster', ''), 'fanart': meta.get('background', ''), 'clearlogo': cached_logo, 'logo': cached_logo, 'tvshow.clearlogo': cached_logo})
            else:
                list_item.setArt({'poster': meta.get('poster', ''), 'thumb': meta.get('poster', ''), 'fanart': meta.get('background', ''), 'clearlogo': logo_url, 'logo': logo_url, 'tvshow.clearlogo': logo_url})
        elif meta.get('poster'):
            list_item.setArt({'poster': meta['poster'], 'thumb': meta['poster']})
        if meta.get('background') and not logo_url:
            list_item.setArt({'fanart': meta['background']})

        # Add season context menu
        context_menu = []

        # Add Trakt watched toggle for season if authorized
        if HAS_MODULES and trakt.get_access_token():
            # Use season watched status (already calculated above)
            if is_season_watched:
                context_menu.append(('[COLOR lightcoral]Mark Season As Unwatched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_unwatched", media_type="show", imdb_id=meta_id, season=season_num)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Season As Watched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_watched", media_type="show", imdb_id=meta_id, season=season_num)})'))

        list_item.addContextMenuItems(context_menu)
        
        url = get_url(action='show_episodes', meta_id=meta_id, season=season_num)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)



def youtube_menu():
    """Show static YouTube menu items."""
    youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
    imvdb_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.imvdb)')
    
    if not youtube_available and not imvdb_available:
        xbmcgui.Dialog().notification('AIOStreams', 'Music Video addons not installed', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    
    if youtube_available:
        items = [
            ('Search', 'plugin://plugin.video.youtube/search/?path=/root/search', 'DefaultAddonsSearch.png'),
            ('Playlists', 'plugin://plugin.video.youtube/playlists/', 'DefaultPlaylist.png'),
            ('Bookmarks', 'plugin://plugin.video.youtube/special/watch_later/', 'DefaultFolder.png')
        ]

        for label, url, icon in items:
            list_item = xbmcgui.ListItem(label=label)
            list_item.setArt({'icon': icon, 'thumb': icon})
            list_item.setInfo('video', {'title': label})
            # YouTube plugin items are folders
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    xbmcplugin.endOfDirectory(HANDLE)


def browse_show():
    """Open custom browse window for TV show with seasons and episodes."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    meta_id = params['meta_id']
    
    meta_data = get_meta('series', meta_id)
    
    if not meta_data or 'meta' not in meta_data:
        xbmcgui.Dialog().notification('AIOStreams', 'Series info not found', xbmcgui.NOTIFICATION_ERROR)
        return
    
    meta = meta_data['meta']
    series_name = meta.get('name', 'Unknown Series')
    
    videos = meta.get('videos', [])
    
    if not videos:
        xbmcgui.Dialog().notification('AIOStreams', 'No seasons found', xbmcgui.NOTIFICATION_INFO)
        return
    
    # Group episodes by season
    seasons = {}
    for video in videos:
        season = video.get('season')
        if season is not None:
            if season not in seasons:
                seasons[season] = []
            seasons[season].append(video)
    
    # Set window properties for the show
    window = xbmcgui.Window(10000)  # Home window for properties
    window.setProperty('BrowseShow.Title', series_name)
    window.setProperty('BrowseShow.MetaID', meta_id)
    
    if meta.get('poster'):
        window.setProperty('BrowseShow.Poster', meta['poster'])
    if meta.get('background'):
        window.setProperty('BrowseShow.Fanart', meta['background'])
    if meta.get('plot'):
        window.setProperty('BrowseShow.Plot', meta['plot'])
    
    # Set season count
    window.setProperty('BrowseShow.SeasonCount', str(len(seasons)))
    
    # Activate the custom browse window
    xbmc.executebuiltin('ActivateWindow(1114)')


def show_episodes():
    """Show episodes for a specific season."""
    from resources.lib import trakt
    params = dict(parse_qsl(sys.argv[2][1:]))
    meta_id = params['meta_id']
    season = int(params['season'])
    
    # === DB OPTIMIZATION: Try local SyncDB first ===
    meta_data = None
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        db = TraktSyncDatabase()
        
        # Resolve Trakt ID if needed
        trakt_id = None
        if isinstance(meta_id, int) or (isinstance(meta_id, str) and meta_id.isdigit()):
             trakt_id = int(meta_id)
        elif isinstance(meta_id, str) and meta_id.startswith('tt'):
             trakt_id = db.get_trakt_id_for_item(meta_id, 'show')
             
        if trakt_id:
             # Try to get show data from local DB
             show_row = db.get_show(trakt_id)
             if show_row and show_row.get('metadata'):
                 show_meta = show_row['metadata']
                 # Try to get episodes from local DB
                 episode_rows = db.get_episodes_for_show(trakt_id)
                 if episode_rows:
                     videos = []
                     for row in episode_rows:
                         ep_data = row.get('metadata', {}) or {}
                         # Ensure minimal keys
                         if 'season' not in ep_data: ep_data['season'] = row['season']
                         if 'episode' not in ep_data: ep_data['episode'] = row['episode']
                         videos.append(ep_data)
                     
                     show_meta['videos'] = videos
                     # Construct the 'meta_data' structure expected below
                     meta_data = {'meta': show_meta}
                     xbmc.log(f'[AIOStreams] Loaded {len(videos)} episodes from local SyncDB for Season {season}', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] SyncDB optimization error: {e}', xbmc.LOGERROR)

    if not meta_data:
        meta_data = get_meta('series', meta_id)
    
    if not meta_data or 'meta' not in meta_data:
        xbmcgui.Dialog().notification('AIOStreams', 'Series info not found', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    meta = meta_data['meta']
    series_name = meta.get('name', 'Unknown Series')
    
    series_name = meta.get('name', 'Unknown Series')
    
    # Set window-level artwork properties for the skin
    logo_url = meta.get('logo')
    if logo_url:
        cached_logo = get_cached_clearlogo_path('series', meta_id)
        win = xbmcgui.Window(10000)
        win.setProperty('AIOStreams_ShowLogo', cached_logo or logo_url)
        win.setProperty('AIOStreams_HasLogo', 'true')
        if not cached_logo:
             _ensure_clearlogo_cached(meta, 'series', meta_id)
    else:
        xbmcgui.Window(10000).setProperty('AIOStreams_HasLogo', 'false')

    xbmcplugin.setPluginCategory(HANDLE, f'{series_name} - Season {season}')
    xbmcplugin.setContent(HANDLE, 'episodes')
    
    videos = meta.get('videos', [])
    xbmc.log(f'[AIOStreams] show_episodes: Searching for Season {season} in {len(videos)} videos', xbmc.LOGINFO)
    
    episodes = []
    for v in videos:
        v_season = v.get('season')
        if v_season == season:
            episodes.append(v)
        else:
            # excessive logging, maybe just log first mismatch
            pass
            
    xbmc.log(f'[AIOStreams] show_episodes: Found {len(episodes)} matching episodes', xbmc.LOGINFO)
    
    if not episodes:
        xbmcgui.Dialog().notification('AIOStreams', 'No episodes found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    episodes.sort(key=lambda x: x.get('episode', 0))

    # Get Trakt data once for all episodes (performance optimization)
    watched_episodes = set()
    show_in_watchlist = False
    is_season_watched = False

    if HAS_MODULES and trakt.get_access_token():
        # Get show progress to determine watched episodes
        show_progress = trakt.get_show_progress(meta_id)
        if show_progress:
            seasons_data = show_progress.get('seasons', [])
            for s in seasons_data:
                if s.get('number') == season:
                    # Build set of watched episode numbers for this season
                    for ep in s.get('episodes', []):
                        if ep.get('completed', False):
                            watched_episodes.add(ep.get('number'))
                    # Check if entire season is watched
                    aired = s.get('aired', 0)
                    completed = s.get('completed', 0)
                    is_season_watched = aired > 0 and aired == completed
                    break

        # Check if show is in watchlist (once for all episodes)
        show_in_watchlist = trakt.is_in_watchlist('series', meta_id)

    # Display episodes
    for episode in episodes:
        episode_num = episode.get('episode', 0)
        episode_title = episode.get('title', f'Episode {episode_num}')

        # Check watch status from cached data
        is_watched = episode_num in watched_episodes
        progress = 100 if is_watched else 0

        # Format episode label with UI enhancements
        if HAS_MODULES:
            label = ui_helpers.format_episode_title(episode_num, episode_title, is_watched, progress)
        else:
            label = f'{episode_num}. {episode_title}'

        list_item = xbmcgui.ListItem(label=label)

        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(episode_title)
        info_tag.setEpisode(episode_num)
        info_tag.setSeason(season)
        info_tag.setTvShowTitle(series_name)
        info_tag.setPlot(episode.get('overview', ''))
        info_tag.setMediaType('episode')

        # Add episode runtime (same parsing logic as movies/shows)
        episode_runtime = episode.get('runtime', '')
        if episode_runtime:
            try:
                runtime_str = str(episode_runtime).lower()
                total_minutes = 0

                # Handle "2h16min" format
                if 'h' in runtime_str:
                    parts = runtime_str.split('h')
                    hours = int(parts[0].strip())
                    total_minutes = hours * 60
                    if len(parts) > 1 and parts[1]:
                        mins = parts[1].replace('min', '').replace('minutes', '').strip()
                        if mins:
                            total_minutes += int(mins)
                else:
                    # Handle "48min" or "58" format
                    mins = runtime_str.replace('min', '').replace('minutes', '').strip()
                    total_minutes = int(mins)

                if total_minutes > 0:
                    info_tag.setDuration(total_minutes * 60)  # Convert to seconds
            except:
                pass

        # Add episode premiered date (format properly from ISO date)
        released = episode.get('released', '')
        if released:
            try:
                # Extract date in YYYY-MM-DD format from ISO date
                premiered_date = released.split('T')[0]  # "2008-01-20T12:00:00.000Z" -> "2008-01-20"
                info_tag.setPremiered(premiered_date)
            except:
                pass

        if episode.get('thumbnail'):
            list_item.setArt({'thumb': episode['thumbnail']})
        elif meta.get('poster'):
            list_item.setArt({'thumb': meta['poster']})

        if meta.get('background'):
            list_item.setArt({'fanart': meta['background']})
            
        # Set clearlogo for episode from series meta
        logo_url = meta.get('logo')
        if logo_url:
            cached_logo = get_cached_clearlogo_path('series', meta_id)
            if cached_logo:
                list_item.setArt({'clearlogo': cached_logo, 'logo': cached_logo, 'tvshow.clearlogo': cached_logo})
            else:
                list_item.setArt({'clearlogo': logo_url, 'logo': logo_url, 'tvshow.clearlogo': logo_url})
                _ensure_clearlogo_cached(meta, 'series', meta_id)

        # Set playcount if watched
        if is_watched:
            info_tag.setPlaycount(1)
            list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')

        # Add episode context menu
        episode_title = f'{series_name} - S{season:02d}E{episode_num:02d}'
        episode_media_id = f"{meta_id}:{season}:{episode_num}"
        episode_poster = meta.get('poster', '')
        episode_fanart = meta.get('background', '')
        episode_clearlogo = meta.get('logo', '')
        context_menu = [
            ('[COLOR lightcoral]Scrape Streams[/COLOR]', f'RunPlugin({get_url(action="show_streams", content_type="series", media_id=episode_media_id, title=episode_title, poster=episode_poster, fanart=episode_fanart, clearlogo=episode_clearlogo)})'),
            ('[COLOR lightcoral]Browse Show[/COLOR]', f'ActivateWindow(Videos,{sys.argv[0]}?{urlencode({"action": "show_seasons", "meta_id": meta_id})},return)')
        ]

        # Add Trakt watched toggle if authorized
        if HAS_MODULES and trakt.get_access_token():
            if is_watched:
                context_menu.append(('[COLOR lightcoral]Mark Episode As Unwatched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_unwatched", media_type="show", imdb_id=meta_id, season=season, episode=episode_num)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Episode As Watched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_watched", media_type="show", imdb_id=meta_id, season=season, episode=episode_num)})'))

        list_item.addContextMenuItems(context_menu)

        # Make episodes directly playable
        url = get_url(action='play', content_type='series', imdb_id=meta_id, season=season, episode=episode_num, title=episode_title, poster=episode_poster, fanart=episode_fanart, clearlogo=episode_clearlogo)
        list_item.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)
    
    xbmcplugin.endOfDirectory(HANDLE)


# Trakt functions
def trakt_menu():
    """Trakt catalogs submenu."""
    from resources.lib import trakt
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return
    
    xbmcplugin.setPluginCategory(HANDLE, 'Trakt Catalogs')
    xbmcplugin.setContent(HANDLE, 'videos')
    
    menu_items = [
        {'label': 'Next Up', 'url': get_url(action='trakt_next_up'), 'icon': 'DefaultTVShows.png'},
        {'label': 'Watchlist - Movies', 'url': get_url(action='trakt_watchlist', media_type='movies'), 'icon': 'DefaultMovies.png'},
        {'label': 'Watchlist - Shows', 'url': get_url(action='trakt_watchlist', media_type='shows'), 'icon': 'DefaultTVShows.png'},
        # Trakt Collections and Recommendations removed per user request
    ]
    
    for item in menu_items:
        list_item = xbmcgui.ListItem(label=item['label'])
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(item['label'])
        list_item.setArt({'icon': item['icon']})
        xbmcplugin.addDirectoryItem(HANDLE, item['url'], list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def force_trakt_sync():
    """Force immediate Trakt sync with progress dialog."""
    from resources.lib import trakt
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return
    
    from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
    
    db = TraktSyncDatabase()
    result = db.sync_activities(silent=False)  # Show progress dialog
    
    if result is None:
        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Sync throttled (wait 5 minutes)',
            xbmcgui.NOTIFICATION_INFO
        )
    elif result:
        xbmc.log('[AIOStreams] Force sync completed successfully', xbmc.LOGINFO)
    else:
        xbmc.log('[AIOStreams] Force sync completed with errors', xbmc.LOGWARNING)


def trakt_watchlist(params=None):
    """Display Trakt watchlist with auto-sync."""
    from resources.lib import trakt
    # Suppression guard
    # Suppression guard (Global or Internal)
    win_home = xbmcgui.Window(10000)
    if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
       win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
        xbmc.log('[AIOStreams] Suppression: trakt_watchlist skipped (Search Active)', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
        return

    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    # CRITICAL FIX: Respect params argument if provided (used by smart_widget)
    if params is None:
        params = dict(parse_qsl(sys.argv[2][1:]))
    
    media_type = params.get('media_type', 'movies')
    items = []

    # Auto-sync if enabled (throttled to 5 minutes)
    auto_sync_enabled = get_setting('trakt_sync_auto', 'true') == 'true'
    if auto_sync_enabled:
        try:
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
            db = TraktSyncDatabase()
            db.sync_activities(silent=True)  # Silent auto-sync
        except Exception as e:
            xbmc.log(f'[AIOStreams] Auto-sync failed: {e}', xbmc.LOGWARNING)
    
    # Try fetching from database first (instant)
    try:
        from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
        db = TraktSyncDatabase()
        
        # Query watchlist from database using helper which unpickles metadata
        mediatype_filter = 'movie' if media_type == 'movies' else 'show'
        items_raw = db.get_watchlist_items(mediatype_filter)
        
        if items_raw:
            # Convert database format to Trakt API format for compatibility
            content_key = media_type[:-1] if media_type.endswith('s') else media_type
            for row in items_raw:
                try:
                    # Use metadata if available (contains extended info)
                    # sqlite3.Row uses dictionary-style access, not .get()
                    metadata = row['metadata'] if 'metadata' in row.keys() else None
                    if metadata:
                        item_data = metadata
                    else:
                        item_data = {
                            'ids': {
                                'trakt': row['trakt_id'] if 'trakt_id' in row.keys() else None,
                                'imdb': row['imdb_id'] if 'imdb_id' in row.keys() else None
                            }
                        }

                    item_wrapper = {
                        'listed_at': row['listed_at'] if 'listed_at' in row.keys() else None,
                        content_key: item_data
                    }
                    items.append(item_wrapper)
                except Exception as e:
                    xbmc.log(f'[AIOStreams] Error unpacking watchlist row: {e}', xbmc.LOGWARNING)
                    continue
            xbmc.log(f'[AIOStreams] Watchlist: Loaded {len(items)} items from database', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error accessing watchlist database: {e}', xbmc.LOGWARNING)

    # Fallback to old Trakt API method if database is empty or failed
    if not items:
        xbmc.log('[AIOStreams] Watchlist database empty/failed, using Trakt API', xbmc.LOGDEBUG)
        items = trakt.get_watchlist(media_type)

    if not items:
        xbmcgui.Dialog().notification('AIOStreams', 'Watchlist is empty', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Trakt Watchlist - {media_type.capitalize()}')
    xbmcplugin.setContent(HANDLE, 'movies' if media_type == 'movies' else 'tvshows')

    # Prepare items for parallel fetching
    items_to_fetch = []
    for item in items:
        item_data = item.get('movie' if media_type == 'movies' else 'show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')
        if item_id:
            items_to_fetch.append({'ids': {'imdb': item_id}})

    # Parallel fetch all metadata
    xbmc.log(f'[AIOStreams] Watchlist: Fetching metadata for {len(items_to_fetch)} items in parallel...', xbmc.LOGINFO)
    content_type_fetch = 'movie' if media_type == 'movies' else 'series'
    metadata_map = fetch_metadata_parallel(items_to_fetch, content_type=content_type_fetch)

    for item in items:
        item_data = item.get('movie' if media_type == 'movies' else 'show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')

        if not item_id:
            continue

        content_type = 'movie' if media_type == 'movies' else 'series'

        # Build metadata from Trakt data (no API call needed for text fields)
        meta = {
            'id': item_id,
            'name': item_data.get('title', 'Unknown'),
            'description': item_data.get('overview', ''),
            'year': item_data.get('year', 0),
            'genres': item_data.get('genres', []),
            'imdbRating': str(item_data.get('rating', '')) if item_data.get('rating') else ''
        }

        # Use fetched metadata (parallel results)
        if item_id in metadata_map:
            cached_data = metadata_map[item_id]
            
            # Enhance with cached artwork and other metadata
            meta['poster'] = cached_data.get('poster', '')
            meta['background'] = cached_data.get('background', '')
            meta['logo'] = cached_data.get('logo', '')
            
            # CRITICAL FIX: If Trakt title is missing or "Unknown", use AIOStreams Title
            cached_title = cached_data.get('title') or cached_data.get('name', '')
            if (not meta.get('name') or meta['name'] == 'Unknown') and cached_title:
                meta['name'] = cached_title
            
            # Use cached description if Trakt description is empty
            if not meta.get('description') and cached_data.get('description'):
                meta['description'] = cached_data['description']
                
            # Get cast from cached AIOStreams data (includes photos)
            if 'cast' in cached_data:
                meta['cast'] = cached_data['cast']

        # Set URL and folder status based on content type
        if content_type == 'series':
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        else:
            url = get_url(action='play', content_type='movie', imdb_id=item_id, title=meta.get('name', ''), 
                         poster=meta.get('poster', ''), fanart=meta.get('background', ''), clearlogo=meta.get('logo', ''))
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    # Set NumItems property if called from smart_widget
    if params.get('page') and params.get('index'):
        count_prop = f"AIOStreams.{params['page']}.{params['index']}.NumItems"
        xbmcgui.Window(10000).setProperty(count_prop, str(len(items)))
        xbmc.log(f'[AIOStreams] Set {count_prop} = {len(items)}', xbmc.LOGDEBUG)

    xbmcplugin.endOfDirectory(HANDLE)


def trakt_recommendations(params=None):
    """Display personalized Trakt recommendations - REMOVED PER USER REQUEST."""
    xbmcgui.Dialog().notification('AIOStreams', 'Feature Removed', xbmcgui.NOTIFICATION_INFO)
    xbmcplugin.endOfDirectory(HANDLE)


def trakt_collection():
    """Display Trakt collection - REMOVED PER USER REQUEST."""
    xbmcgui.Dialog().notification('AIOStreams', 'Feature Removed', xbmcgui.NOTIFICATION_INFO)
    xbmcplugin.endOfDirectory(HANDLE)






def trakt_next_up():
    """Display next episodes to watch using pure SQL - ZERO API calls!

    Uses Seren's approach: calculates next episode from local database.
    All episodes are stored during sync, so we can find the next unwatched
    episode purely from SQL without calling the API.
    """
    from resources.lib import trakt
    # Suppression guard
    # Suppression guard (Global or Internal)
    win_home = xbmcgui.Window(10000)
    if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
       win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
        xbmc.log('[AIOStreams] Suppression: trakt_next_up skipped (Search Active)', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
        return

    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Next Up')
    xbmcplugin.setContent(HANDLE, 'episodes')
    
    # Prime database cache (batch fetch watched status)
    try:
        from resources.lib import trakt
        trakt.prime_database_cache()
    except:
        pass

    # Get next episodes from database - ONE SQL query, ZERO API calls!
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        db = TraktSyncDatabase()
        next_episodes = db.get_next_up_episodes()
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error getting next up from database: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Error loading Next Up', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if not next_episodes:
        xbmc.log('[AIOStreams] DEBUG: trakt_next_up - No shows in progress (next_episodes list is empty)', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'No shows in progress', xbmcgui.NOTIFICATION_INFO)
        
        # Fallback item for visual confirmation
        li = xbmcgui.ListItem(label='[No Next Up Episodes Found]')
        li.setInfo('video', {'plot': 'Trakt returned no next up episodes.\nCheck your Trakt history or scrobbling status.'})
        url = get_url(action='noop')
        xbmcplugin.addDirectoryItem(HANDLE, url, li, False)
        
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmc.log(f'[AIOStreams] Next Up: Found {len(next_episodes)} shows with next episodes', xbmc.LOGINFO)

    xbmc.log(f'[AIOStreams] Next Up: Found {len(next_episodes)} shows with next episodes', xbmc.LOGINFO)

    # Prepare item list for parallel fetching
    items_to_fetch = []
    for ep in next_episodes:
        show_imdb = ep.get('show_imdb_id')
        if show_imdb:
            items_to_fetch.append({'ids': {'imdb': show_imdb}})
            
    # Fetch all metadata in parallel
    xbmc.log(f'[AIOStreams] Next Up: Fetching metadata for {len(items_to_fetch)} items in parallel...', xbmc.LOGINFO)
    metadata_map = fetch_metadata_parallel(items_to_fetch, content_type='series')
    xbmc.log(f'[AIOStreams] Next Up: Metadata fetch complete', xbmc.LOGINFO)

    # Set NumItems property if called from smart_widget
    # We check sys.argv for widget=true or similar if not passed in params
    params = dict(parse_qsl(sys.argv[2][1:]))
    if params.get('page') and params.get('index'):
        count_prop = f"AIOStreams.{params['page']}.{params['index']}.NumItems"
        xbmcgui.Window(10000).setProperty(count_prop, str(len(next_episodes)))
        xbmc.log(f'[AIOStreams] Set {count_prop} = {len(next_episodes)}', xbmc.LOGDEBUG)

    def process_ep(ep_data):
        try:
            show_imdb = ep_data.get('show_imdb_id', '')
            show_title = ep_data.get('show_title', 'Unknown')
            season = ep_data.get('season', 0)
            episode = ep_data.get('episode', 0)
            episode_imdb = ep_data.get('episode_imdb_id', '')

            # Get AIOStreams metadata for artwork (fetch from API if not cached)
            poster = ''
            fanart = ''
            logo = ''
            episode_thumb = ''
            episode_title = f'Episode {episode}'
            episode_overview = ''
            # Get air date from database query (already included in ep_data)
            episode_air_date = ep_data.get('air_date', '')

            # 1. First, try to get episode-specific metadata from database (instant!)
            episode_meta = ep_data.get('episode_metadata')
            if episode_meta:
                episode_title = episode_meta.get('title', episode_title)
                episode_overview = episode_meta.get('overview', '')
                if not episode_air_date:
                    episode_air_date = episode_meta.get('first_aired', '') or episode_meta.get('aired', '')

            # 2. Get show metadata from our parallel fetch results
            meta_data = None
            if show_imdb and show_imdb in metadata_map:
                meta_data = metadata_map[show_imdb]
            
            # If not in map, try local DB (might have been missed or failed)
            if not meta_data and show_imdb:
                 meta_data = ep_data.get('show_metadata')

            # Extract artwork from show metadata
            if meta_data:
                # Get show title from metadata if available
                show_title = meta_data.get('name', show_title)
                poster = meta_data.get('poster', '')
                fanart = meta_data.get('background', '')
                logo = meta_data.get('logo', '')

                # Try to get episode thumbnail from show metadata videos (fallback if not in DB)
                if not episode_thumb:
                    videos = meta_data.get('videos', [])
                    for video in videos:
                        if video.get('season') == season and video.get('episode') == episode:
                            episode_thumb = video.get('thumbnail', '')
                            # Only override episode title/overview if not already from DB
                            if not episode_meta:
                                episode_title = video.get('title', episode_title)
                                episode_overview = video.get('description', '')
                                # Also try to get air date from video metadata
                                if not episode_air_date:
                                    episode_air_date = video.get('released', '') or video.get('first_aired', '')
                            break

            label = f'{show_title} S{season:02d}E{episode:02d}'

            list_item = xbmcgui.ListItem(label=label)
            info_tag = list_item.getVideoInfoTag()
            info_tag.setTitle(episode_title)
            info_tag.setTvShowTitle(show_title)
            info_tag.setSeason(season)
            info_tag.setEpisode(episode)
            info_tag.setMediaType('episode')
            xbmc.log(f'[AIOStreams] Processing episode S{season}E{episode}: setMediaType("episode") called', xbmc.LOGDEBUG)
            info_tag.setPlot(episode_overview)
            
            # Set air date if available (shows in subtitle)
            if episode_air_date:
                air_date_str = episode_air_date.split('T')[0] if 'T' in episode_air_date else episode_air_date
                info_tag.setPremiered(air_date_str)
                info_tag.setFirstAired(air_date_str)
                formatted_date = format_date_with_ordinal(air_date_str)
                list_item.setProperty('AirDate', formatted_date)
                list_item.setLabel2(formatted_date)

            # Set artwork
            art = {}
            if episode_thumb:
                art['thumb'] = episode_thumb
                if poster:
                    art['poster'] = poster
            elif poster:
                art['thumb'] = poster
                art['poster'] = poster
            
            if fanart:
                art['fanart'] = fanart
            
            if logo:
                # Check for cached logo (fast check)
                cached_logo = get_cached_clearlogo_path('series', show_imdb)
                if cached_logo:
                    art['clearlogo'] = cached_logo
                    art['logo'] = cached_logo
                    # xbmc.log(f'[AIOStreams] Used cached clearlogo for {show_title}: {cached_logo}', xbmc.LOGDEBUG)
                else:
                    xbmc.log(f'[AIOStreams] No cached logo for {show_title}, using URL: {logo}', xbmc.LOGDEBUG)
                    art['clearlogo'] = logo
                    art['logo'] = logo
                    # Ensure it's getting cached (background)
                    _ensure_clearlogo_cached({'meta': {'logo': logo}}, 'series', show_imdb)

                # Update ep_data for window properties
                ep_data['Logo'] = art['clearlogo']
                
            if art:
                list_item.setArt(art)

            # Enhancement: Add Director, Duration
            if meta_data:
                runtime = meta_data.get('runtime', 0)
                if runtime:
                    try:
                        info_tag.setDuration(int(runtime) * 60)
                    except: pass
                
                # Add Directors
                if meta_data.get('director'):
                     info_tag.setDirectors([d.strip() for d in str(meta_data['director']).split(',') if d.strip()])

            # Add PercentPlayed and Watched status from database
            try:
                # Set MediaType property for skin assist
                list_item.setProperty('MediaType', 'episode')
                
                # Check for progress data in joined query result
                percent = ep_data.get('percent_played', 0)
                xbmc.log(f'[AIOStreams] Episode S{season}E{episode}: percent_played from query = {percent}', xbmc.LOGDEBUG)
                
                if percent and percent > 0:
                    list_item.setProperty('PercentPlayed', str(int(percent)))
                    info_tag.setPercentPlayed(float(percent))
                    xbmc.log(f'[AIOStreams] Set PercentPlayed property and info_tag for S{season}E{episode} to {percent}%', xbmc.LOGINFO)
                    resume_time = ep_data.get('resume_time', 0)
                    if resume_time > 0:
                        list_item.setProperty('StartOffset', str(resume_time))
                else:
                    # Fallback to separate lookup if not in joined result
                    # Extract all available IDs from episode metadata
                    episode_trakt_id = ep_data.get('episode_trakt_id')
                    
                    # Try to get IDs from episode metadata
                    episode_meta = ep_data.get('episode_metadata')
                    episode_tvdb = None
                    episode_tmdb = None
                    episode_imdb = ep_data.get('episode_imdb_id')
                    
                    if episode_meta and isinstance(episode_meta, dict):
                        ids = episode_meta.get('ids', {})
                        episode_tvdb = ids.get('tvdb')
                        episode_tmdb = ids.get('tmdb')
                        if not episode_imdb:
                            episode_imdb = ids.get('imdb')
                    
                    if episode_trakt_id or episode_tvdb or episode_tmdb or episode_imdb:
                        bookmark = db.get_bookmark(
                            trakt_id=episode_trakt_id,
                            tvdb_id=episode_tvdb,
                            tmdb_id=episode_tmdb,
                            imdb_id=episode_imdb
                        )
                        if bookmark:
                            percent = bookmark.get('percent_played', 0)
                            if percent > 0:
                                list_item.setProperty('PercentPlayed', str(int(percent)))
                                info_tag.setPercentPlayed(float(percent))
                                xbmc.log(f'[AIOStreams] Set PercentPlayed from fallback for S{season}E{episode} to {percent}%', xbmc.LOGINFO)
                                resume_time = bookmark.get('resume_time', 0)
                                if resume_time > 0:
                                    list_item.setProperty('StartOffset', str(resume_time))

                show_trakt_id = ep_data.get('show_trakt_id')
                if show_trakt_id:
                    is_watched = db.is_item_watched(show_trakt_id, 'episode', season, episode)
                    if is_watched:
                        info_tag.setPlaycount(1)
                        list_item.setProperty('watched', 'true')
                        list_item.setProperty('WatchedOverlay', 'indicator_watched.png')
            except:
                pass

            # Build context menu
            episode_media_id = f"{show_imdb}:{season}:{episode}"
            episode_title_str = f'{show_title} - S{season:02d}E{episode:02d}'
            context_menu = [
                ('[COLOR lightcoral]Scrape Streams[/COLOR]', f'RunPlugin({get_url(action="show_streams", content_type="series", media_id=episode_media_id, title=episode_title_str, poster=poster, fanart=fanart, clearlogo=logo)})'),
                ('[COLOR lightcoral]Browse Show[/COLOR]', f'ActivateWindow(Videos,{sys.argv[0]}?{urlencode({"action": "show_seasons", "meta_id": show_imdb})},return)')
            ]

            if HAS_MODULES and trakt.get_access_token() and show_imdb:
                is_episode_watched = trakt.is_episode_watched(show_imdb, season, episode)
                if is_episode_watched:
                    context_menu.append(('[COLOR lightcoral]Mark Episode As Unwatched[/COLOR]',
                                        f'RunPlugin({get_url(action="trakt_mark_unwatched", media_type="show", imdb_id=show_imdb, season=season, episode=episode)})'))
                else:
                    context_menu.append(('[COLOR lightcoral]Mark Episode As Watched[/COLOR]',
                                        f'RunPlugin({get_url(action="trakt_mark_watched", media_type="show", imdb_id=show_imdb, season=season, episode=episode)})'))
                
                context_menu.append(('[COLOR lightcoral]Stop Watching (Drop) Trakt[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_hide_from_progress", media_type="series", imdb_id=show_imdb)})'))

            if context_menu:
                list_item.addContextMenuItems(context_menu)

            if show_imdb:
                url = get_url(action='play', content_type='series', imdb_id=show_imdb, season=season, episode=episode, title=episode_title_str, poster=poster, fanart=fanart, clearlogo=logo)
                list_item.setProperty('IsPlayable', 'true')
                
                air_date = ep_data.get('air_date')
                if air_date:
                    formatted_date = format_date_with_ordinal(air_date)
                    list_item.setProperty('AiredDate', formatted_date)
                    
            return (url, list_item, False)
        
        except Exception as e:
            return None

    # Execute processing (lightweight now since metadata is pre-fetched)
    for ep in next_episodes:
        result = process_ep(ep)
        if result:
             xbmcplugin.addDirectoryItem(HANDLE, result[0], result[1], result[2])

    # Push Next Up data to window properties for instant widget updates
    _push_next_up_to_window(next_episodes)
    
    # Force container refresh to solve widget delay
    xbmc.executebuiltin('Container.Refresh')

    xbmcplugin.endOfDirectory(HANDLE)


def show_related():
    """Show related/similar content."""
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return
    
    from resources.lib import trakt

    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params.get('content_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    title = params.get('title', 'Unknown')

    if not imdb_id:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Similar to {title}')
    xbmcplugin.setContent(HANDLE, 'movies' if content_type == 'movie' else 'tvshows')

    # Get related items from Trakt
    items = trakt.get_related(content_type, imdb_id, page=1, limit=20)

    if not items:
        xbmcgui.Dialog().notification('AIOStreams', 'No related content found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Prepare for parallel fetch (handle mixed content types)
    movie_items = []
    show_items = []
    
    for item in items:
        item_type = 'movie' if 'movie' in item else 'show'
        item_data = item.get('movie') or item.get('show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')
        if item_id:
            if item_type == 'movie':
                movie_items.append({'ids': {'imdb': item_id}})
            else:
                show_items.append({'ids': {'imdb': item_id}})
    
    # Parallel fetch all metadata
    metadata_map = {}
    if movie_items:
        xbmc.log(f'[AIOStreams] Related: Fetching {len(movie_items)} movies in parallel...', xbmc.LOGINFO)
        metadata_map.update(fetch_metadata_parallel(movie_items, 'movie'))
    if show_items:
        xbmc.log(f'[AIOStreams] Related: Fetching {len(show_items)} shows in parallel...', xbmc.LOGINFO)
        metadata_map.update(fetch_metadata_parallel(show_items, 'series'))

    # Display related items
    for item in items:
        item_type = 'movie' if 'movie' in item else 'show'
        item_data = item.get('movie') or item.get('show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')

        if not item_id:
            continue

        # Use the correct content type for this specific item
        item_content_type = 'movie' if item_type == 'movie' else 'series'

        # Use parallel result if available
        meta = None
        if item_id in metadata_map:
            meta = metadata_map[item_id]
        else:
            # Fallback (should typically be covered by parallel fetch)
            meta_data = get_meta(item_content_type, item_id)
            if meta_data and 'meta' in meta_data:
                meta = meta_data['meta']

        if not meta:
            meta = {
                'id': item_id,
                'name': item_data.get('title', 'Unknown'),
                'description': item_data.get('overview', ''),
                'year': item_data.get('year', 0),
                'genres': []
            }

        if item_content_type == 'series':
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        else:
            title = meta.get('name', 'Unknown')
            poster = meta.get('poster', '')
            fanart = meta.get('background', '')
            clearlogo = meta.get('logo', '')
            url = get_url(action='play', content_type='movie', imdb_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
            is_folder = False

        list_item = create_listitem_with_context(meta, item_content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def trakt_hide_show():
    """Hide a show from progress."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return
    
    params = dict(parse_qsl(sys.argv[2][1:]))
    show_trakt_id = params.get('show_trakt_id', '')
    
    if show_trakt_id:
        trakt.hide_show_from_progress(int(show_trakt_id))
        xbmc.executebuiltin('Container.Refresh')


def trakt_auth():
    """Authorize with Trakt."""
    from resources.lib import trakt
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return
    
    trakt.authorize()


def trakt_revoke():
    """Revoke Trakt authorization."""
    from resources.lib import trakt
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    trakt.revoke_authorization()


# Helper functions for Trakt actions
def _get_params():
    """Get URL parameters as dict."""
    return dict(parse_qsl(sys.argv[2][1:]))


def _refresh_ui():
    """Refresh container and trigger background widget refresh."""
    # Clear Trakt widget cache so Next Up and Watchlist refresh with new data
    _clear_trakt_widget_cache()
    
    # Update WidgetReloadToken skin string to force immediate background refresh
    try:
        current_token = xbmc.getSkinVariableString('WidgetReloadToken')
        new_token = str(int(current_token) + 1) if current_token.isdigit() else "1"
        xbmc.executebuiltin(f'Skin.SetString(WidgetReloadToken,{new_token})')
    except:
        xbmc.executebuiltin('Skin.SetString(WidgetReloadToken,1)')

    xbmc.executebuiltin('Container.Refresh')
    try:
        from resources.lib import utils
        utils.trigger_background_refresh(delay=0.5)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


def _parse_episode_params(params):
    """Parse and convert episode parameters to integers.

    Args:
        params: Dict of URL parameters

    Returns:
        tuple: (season_int, episode_int) or (None, None)
    """
    season = params.get('season')
    episode = params.get('episode')
    season_int = int(season) if season else None
    episode_int = int(episode) if episode else None
    return season_int, episode_int


def _push_next_up_to_window(next_episodes):
    """Push Next Up data to Kodi window properties for instant widget updates.

    This allows skins to access Next Up data without forcing container refresh,
    eliminating the "stutter" effect in widgets.

    Args:
        next_episodes: List of episode dicts from get_next_up_episodes()
    """
    try:
        window = xbmcgui.Window(10000)  # Home window (persistent)

        # Limit to first 20 episodes for performance
        limited_episodes = next_episodes[:20]

        # Push each episode to window properties
        for idx, ep_data in enumerate(limited_episodes):
            show_imdb = ep_data.get('show_imdb_id', '')
            show_title = ep_data.get('show_title', 'Unknown')
            season = ep_data.get('season', 0)
            episode = ep_data.get('episode', 0)
            episode_imdb = ep_data.get('episode_imdb_id', '')
            last_watched = ep_data.get('last_watched_at', '')

            # Set window properties with AIOStreams. prefix
            prefix = f'AIOStreams.NextUp.{idx}'
            window.setProperty(f'{prefix}.ShowTitle', str(show_title))
            window.setProperty(f'{prefix}.ShowIMDB', str(show_imdb))
            window.setProperty(f'{prefix}.Season', str(season))
            window.setProperty(f'{prefix}.Episode', str(episode))
            window.setProperty(f'{prefix}.EpisodeIMDB', str(episode_imdb))
            window.setProperty(f'{prefix}.ClearLogo', str(ep_data.get('Logo', '')))
            window.setProperty(f'{prefix}.Label', f'{show_title} S{season:02d}E{episode:02d}')
            window.setProperty(f'{prefix}.LastWatched', str(last_watched))
            window.setProperty(f'{prefix}.PlayURL', get_url(action='play', content_type='series',
                                                            imdb_id=show_imdb, season=season, episode=episode))

        # Set total count
        window.setProperty('AIOStreams.NextUp.Count', str(len(limited_episodes)))

        # Clear unused slots (in case list got smaller)
        for idx in range(len(limited_episodes), 20):
            prefix = f'AIOStreams.NextUp.{idx}'
            window.clearProperty(f'{prefix}.ShowTitle')
            window.clearProperty(f'{prefix}.ShowIMDB')
            window.clearProperty(f'{prefix}.Season')
            window.clearProperty(f'{prefix}.Episode')
            window.clearProperty(f'{prefix}.EpisodeIMDB')
            window.clearProperty(f'{prefix}.Label')
            window.clearProperty(f'{prefix}.LastWatched')
            window.clearProperty(f'{prefix}.PlayURL')

        xbmc.log(f'[AIOStreams] Pushed {len(limited_episodes)} Next Up items to window properties', xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error pushing Next Up to window properties: {e}', xbmc.LOGERROR)


def _prefetch_next_up_streams(next_episodes):
    """Trigger background prefetch for top Next Up episodes.

    Args:
        next_episodes: List of episode dicts from get_next_up_episodes()
    """
    try:
        from resources.lib.stream_prefetch import get_prefetch_manager

        def get_streams_wrapper(show_imdb, season, episode):
            """Wrapper to fetch streams for an episode."""
            media_id = f"{show_imdb}:{season}:{episode}"
            return get_streams('series', media_id)

        manager = get_prefetch_manager()
        manager.prefetch_streams_async(next_episodes, get_streams_wrapper)

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error triggering stream prefetch: {e}', xbmc.LOGERROR)


def trakt_add_watchlist():
    """Add item to Trakt watchlist."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    params = _get_params()
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        trakt.add_to_watchlist(media_type, imdb_id)
        _refresh_ui()


def trakt_remove_watchlist():
    """Remove item from Trakt watchlist."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    params = _get_params()
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    season_int, episode_int = _parse_episode_params(params)

    if imdb_id:
        trakt.remove_from_watchlist(media_type, imdb_id, season_int, episode_int)
        _refresh_ui()


def trakt_mark_watched():
    """Mark item as watched on Trakt."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    params = _get_params()
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    playback_id = params.get('playback_id', '')
    season_int, episode_int = _parse_episode_params(params)

    if imdb_id:
        playback_id_int = int(playback_id) if playback_id else None
        trakt.mark_watched(media_type, imdb_id, season_int, episode_int, playback_id_int)
        _refresh_ui()


def trakt_mark_unwatched():
    """Mark item as unwatched on Trakt."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    params = _get_params()
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    season_int, episode_int = _parse_episode_params(params)

    if imdb_id:
        trakt.mark_unwatched(media_type, imdb_id, season_int, episode_int)
        _refresh_ui()


def trakt_remove_playback():
    """Remove item from continue watching without marking as watched."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    playback_id = params.get('playback_id', '')

    if playback_id:
        trakt.remove_from_playback(int(playback_id))


def trakt_hide_from_progress():
    """Hide item from Trakt progress (Stop Watching/Drop)."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    params = _get_params()
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        success = trakt.hide_from_progress(media_type, imdb_id)
        if success:
            _refresh_ui()


def trakt_unhide_from_progress():
    """Unhide item from Trakt progress (Undrop/Resume Watching)."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    params = _get_params()
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        success = trakt.unhide_from_progress(media_type, imdb_id)
        if success:
            _refresh_ui()


# Maintenance Tools

def clear_cache():
    """Clear all cached data including Trakt progress cache and manifest."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    try:
        xbmc.log('[AIOStreams] Starting cache clear operation', xbmc.LOGINFO)
        
        # Clear generic caches (manifest, metadata, catalogs, HTTP headers)
        xbmc.log('[AIOStreams] Clearing manifest, metadata, catalog, and HTTP header caches', xbmc.LOGINFO)
        cache.cleanup_expired_cache(force_all=True)
        
        # Also clear Trakt progress caches (memory + disk)
        xbmc.log('[AIOStreams] Clearing Trakt progress caches', xbmc.LOGINFO)
        trakt.invalidate_progress_cache()
        
        # Verify manifest cache was cleared by checking for manifest files
        cache_dir = cache.get_cache_dir()
        remaining_manifests = []
        try:
            import os
            dirs, files = xbmcvfs.listdir(cache_dir)
            for filename in files:
                if filename.startswith('manifest_') and filename.endswith('.json'):
                    remaining_manifests.append(filename)
            
            if remaining_manifests:
                xbmc.log(f'[AIOStreams] Warning: {len(remaining_manifests)} manifest files still present after cleanup', xbmc.LOGWARNING)
            else:
                xbmc.log('[AIOStreams] Manifest cache successfully cleared', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Could not verify manifest cache clear: {e}', xbmc.LOGDEBUG)
        
        xbmc.log('[AIOStreams] Cache clear completed successfully', xbmc.LOGINFO)
        xbmcgui.Dialog().notification('AIOStreams', 'All caches cleared successfully', xbmcgui.NOTIFICATION_INFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to clear cache: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear cache', xbmcgui.NOTIFICATION_ERROR)


def refresh_manifest_cache():
    """Clear manifest cache and fetch fresh manifest from server."""
    if not HAS_MODULES:
        xbmcgui.Dialog().notification('AIOStreams', 'Modules not available', xbmcgui.NOTIFICATION_ERROR)
        return

    try:
        import hashlib

        base_url = get_base_url()
        if not base_url:
            xbmcgui.Dialog().notification('AIOStreams', 'No manifest URL configured', xbmcgui.NOTIFICATION_ERROR)
            return

        # Generate cache key matching the one used in get_manifest()
        cache_key = hashlib.md5(base_url.encode()).hexdigest()[:16]

        xbmc.log(f'[AIOStreams] Clearing manifest cache for key: {cache_key}', xbmc.LOGINFO)

        # Delete the manifest cache file
        cache_dir = cache.get_cache_dir()
        import os
        manifest_path = os.path.join(cache_dir, f'manifest_{cache_key}.json')

        if os.path.exists(manifest_path):
            os.remove(manifest_path)
            xbmc.log(f'[AIOStreams] Deleted manifest cache: {manifest_path}', xbmc.LOGINFO)

        # Also clear from cache module's internal tracking
        cache.cleanup_expired_cache(force_all=False)

        # Now fetch fresh manifest
        xbmc.log('[AIOStreams] Fetching fresh manifest from server', xbmc.LOGINFO)
        manifest = get_manifest()

        if manifest:
            xbmcgui.Dialog().notification(
                'AIOStreams',
                'Manifest cache refreshed successfully',
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            xbmc.log(f'[AIOStreams] Manifest refreshed, catalogs: {len(manifest.get("catalogs", []))}', xbmc.LOGINFO)
        else:
            xbmcgui.Dialog().notification(
                'AIOStreams',
                'Failed to fetch manifest from server',
                xbmcgui.NOTIFICATION_ERROR
            )

    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to refresh manifest cache: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', f'Failed to refresh: {str(e)}', xbmcgui.NOTIFICATION_ERROR)


def clear_stream_stats():
    """Clear stream reliability statistics."""
    if not HAS_MODULES:
        return

    try:
        stream_mgr = streams.get_stream_manager()
        stream_mgr.clear_stats()
        xbmcgui.Dialog().notification('AIOStreams', 'Stream statistics cleared', xbmcgui.NOTIFICATION_INFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to clear stream stats: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear statistics', xbmcgui.NOTIFICATION_ERROR)


def clear_preferences():
    """Clear learned stream preferences."""
    if not HAS_MODULES:
        return

    try:
        stream_mgr = streams.get_stream_manager()
        stream_mgr.clear_preferences()
        xbmcgui.Dialog().notification('AIOStreams', 'Preferences cleared', xbmcgui.NOTIFICATION_INFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to clear preferences: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear preferences', xbmcgui.NOTIFICATION_ERROR)


def clear_trakt_database():
    """Clear all Trakt database data."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return
    
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        
        # Confirm with user
        if not xbmcgui.Dialog().yesno(
            'Clear Trakt Database',
            'This will clear all Trakt data from the local database.',
            'Data will be re-synced on next access.',
            'Continue?'
        ):
            return

        # Clear in-memory caches
        xbmc.log('[AIOStreams] Clearing in-memory caches before database clear', xbmc.LOGINFO)
        trakt.invalidate_progress_cache()

        db = TraktSyncDatabase()
        if not db.connect():
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return
        
        try:
            # Clear all tables
            db.execute('DELETE FROM shows')
            db.execute('DELETE FROM episodes')
            db.execute('DELETE FROM movies')
            db.execute('DELETE FROM watchlist')
            db.execute('DELETE FROM bookmarks')
            db.execute('DELETE FROM hidden')
            db.execute('DELETE FROM activities')
            
            # Clear metadata and catalog caches
            db.execute('DELETE FROM metas')
            db.execute('DELETE FROM catalogs')
            
            db.commit()
            
            xbmc.log('[AIOStreams] Trakt database cleared successfully', xbmc.LOGINFO)
            
            # Clear clearlogo cache
            if clear_clearlogo_cache():
                xbmc.log('[AIOStreams] Clearlogo cache cleared successfully', xbmc.LOGINFO)
            
            xbmcgui.Dialog().notification('AIOStreams', 'All data cleared successfully', xbmcgui.NOTIFICATION_INFO)
        finally:
            db.disconnect()
            
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to clear Trakt database: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear database', xbmcgui.NOTIFICATION_ERROR)


def rebuild_trakt_database():
    """Rebuild Trakt database by clearing and forcing a fresh sync."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return
    
    try:
        # Confirm with user
        if not xbmcgui.Dialog().yesno(
            'Rebuild Trakt Database',
            'This will clear the database and perform a full sync.',
            'This may take a few moments.',
            'Continue?'
        ):
            return

        # Clear in-memory caches FIRST (critical for fixing stale cache bug)
        xbmc.log('[AIOStreams] Clearing in-memory caches before database rebuild', xbmc.LOGINFO)
        trakt.invalidate_progress_cache()

        # Clear database
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        db = TraktSyncDatabase()
        if not db.connect():
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return
        
        try:
            # Clear all tables
            db.execute('DELETE FROM shows')
            db.execute('DELETE FROM episodes')
            db.execute('DELETE FROM movies')
            db.execute('DELETE FROM watchlist')
            db.execute('DELETE FROM bookmarks')
            db.execute('DELETE FROM hidden')
            db.execute('DELETE FROM activities')
            db.commit()
            xbmc.log('[AIOStreams] Database cleared for rebuild', xbmc.LOGINFO)
        finally:
            db.disconnect()
        
        # Force sync
        xbmc.log('[AIOStreams] Starting forced sync after database clear', xbmc.LOGINFO)
        force_trakt_sync()
        
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to rebuild Trakt database: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to rebuild database', xbmcgui.NOTIFICATION_ERROR)


def show_database_info():
    """Show information about all database tables."""
    if not HAS_MODULES:
        return

    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase

        db = TraktSyncDatabase()
        if not db.connect():
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return

        try:
            # Get list of tables that exist
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()] if cursor else []

            # Helper function to safely get count
            def get_table_count(table_name):
                if table_name in existing_tables:
                    result = db.execute(f'SELECT COUNT(*) as count FROM {table_name}').fetchone()
                    return result['count'] if result else 0
                return 0

            # Get counts from each table
            show_count = get_table_count('shows')
            episode_count = get_table_count('episodes')
            movie_count = get_table_count('movies')
            watchlist_count = get_table_count('watchlist')
            hidden_shows_count = get_table_count('hidden_shows')
            stream_stats_count = get_table_count('stream_stats')
            stream_prefs_count = get_table_count('stream_preferences')

            # Get last sync time
            activities = db.fetchone('SELECT last_activities_call FROM activities WHERE sync_id=1')
            if activities and activities.get('last_activities_call'):
                import datetime
                last_sync = datetime.datetime.fromtimestamp(activities['last_activities_call'])
                last_sync_str = last_sync.strftime('%Y-%m-%d %H:%M:%S')
            else:
                last_sync_str = 'Never'

            # Get database file size
            import os
            db_size = 0
            if os.path.exists(db.db_path):
                db_size = os.path.getsize(db.db_path) / 1024  # KB

            info_text = (
                f'Database Statistics:\n\n'
                f'Trakt Data:\n'
                f'  Shows: {show_count}\n'
                f'  Episodes: {episode_count}\n'
                f'  Movies: {movie_count}\n'
                f'  Watchlist: {watchlist_count}\n'
                f'  Hidden Shows: {hidden_shows_count}\n\n'
                f'Stream Data:\n'
                f'  Statistics: {stream_stats_count}\n'
                f'  Preferences: {stream_prefs_count}\n\n'
                f'Last Sync: {last_sync_str}\n'
                f'Database Size: {db_size:.1f} KB'
            )

            xbmcgui.Dialog().ok('Database Info', info_text)

        finally:
            db.disconnect()

    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to get database info: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to get database info', xbmcgui.NOTIFICATION_ERROR)


def database_reset():
    """Complete database reset: clear all tables, caches, and resync Trakt."""
    from resources.lib import trakt
    if not HAS_MODULES:
        return

    # Confirm with user (strong warning)
    confirm = xbmcgui.Dialog().yesno(
        'Database Reset',
        'This will:\n'
        '• Clear ALL database tables\n'
        '• Delete ALL caches\n'
        '• Resync Trakt from scratch\n\n'
        'This action CANNOT be undone!\n\n'
        'Are you sure?'
    )

    if not confirm:
        return
        
    db = Database()
    db.truncate_all()
    
    # Invalidate all caches
    invalidate_progress_cache()
    
    # Clear manifest cache
    from resources.lib.manifest import ManifestManager
    ManifestManager().clear_cache()
    
    xbmcgui.Dialog().notification('Database Reset', 'Core database and caches cleared', xbmcgui.NOTIFICATION_INFO)
    
    # Trigger Trakt re-sync if enabled
    if ADDON.getSettingBool('trakt_sync_auto'):
        from resources.lib import trakt
        trakt.trigger_sync()

def clear_trakt_cache():
    """Specific reset for Trakt sync data to force full re-sync."""
    if not HAS_MODULES:
        return

    # Confirm with user
    confirm = xbmcgui.Dialog().yesno(
        'Clear Trakt Sync',
        'This will clear all local Trakt data and force a full re-sync.\n'
        'Use this if watched status or "Next Up" is incorrect.\n\n'
        'Are you sure?'
    )

    if not confirm:
        return

    try:
        from resources.lib.database.trakt_sync.activities import TraktSyncDatabase as TraktActivities
        db_handler = TraktActivities()
        if db_handler.clear_all_trakt_data():
            xbmcgui.Dialog().notification('Trakt Reset', 'Trakt database cleared. Syncing...', xbmcgui.NOTIFICATION_INFO)
            
            # Start fresh sync
            db_handler.sync_activities(force=True)
        else:
            xbmcgui.Dialog().notification('Trakt Reset', 'Failed to clear Trakt data', xbmcgui.NOTIFICATION_ERROR)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error in clear_trakt_cache: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Error', str(e), xbmcgui.NOTIFICATION_ERROR)
        return


def vacuum_database():
    """Vacuum the Trakt database to optimize and reclaim space."""
    if not HAS_MODULES:
        return
    
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        
        db = TraktSyncDatabase()
        if not db.connect():
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return
        
        try:
            xbmc.log('[AIOStreams] Vacuuming database...', xbmc.LOGINFO)
            db.execute('VACUUM')
            db.commit()
            xbmc.log('[AIOStreams] Database vacuumed successfully', xbmc.LOGINFO)
            xbmcgui.Dialog().notification('AIOStreams', 'Database optimized', xbmcgui.NOTIFICATION_INFO)
        finally:
            db.disconnect()
            
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to vacuum database: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to optimize database', xbmcgui.NOTIFICATION_ERROR)


def quick_actions():
    """Show quick actions menu (for keyboard shortcuts)."""
    from resources.lib import trakt
    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params.get('content_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    title = params.get('title', 'Unknown')
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    clearlogo = params.get('clearlogo', '')

    if not imdb_id:
        xbmcgui.Dialog().notification('AIOStreams', 'No content selected', xbmcgui.NOTIFICATION_ERROR)
        return

    # Build quick actions menu
    actions = [
        'Add to Watchlist (Q)',
        'Mark as Watched (W)',
        'Show Info (I)',
        'Similar Content (S)',
        'Play (Enter)'
    ]

    selected = xbmcgui.Dialog().select(f'Quick Actions: {title}', actions)

    if selected == 0:  # Add to Watchlist
        if HAS_MODULES:
            trakt.add_to_watchlist(content_type, imdb_id)
            xbmc.executebuiltin('Container.Refresh')
    elif selected == 1:  # Mark as Watched
        if HAS_MODULES:
            trakt.mark_watched(content_type, imdb_id)
            xbmc.executebuiltin('Container.Refresh')
    elif selected == 2:  # Show Info
        xbmc.executebuiltin('Action(Info)')
    elif selected == 3:  # Similar Content
        xbmc.executebuiltin(f'Container.Update({get_url(action="show_related", content_type=content_type, imdb_id=imdb_id, title=title)})')
    elif selected == 4:  # Play
        if content_type == 'movie':
            xbmc.executebuiltin(f'RunPlugin({get_url(action="show_streams", content_type="movie", media_id=imdb_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)})')
        else:
            xbmc.executebuiltin(f'Container.Update({get_url(action="show_seasons", meta_id=imdb_id)})')


def test_connection():
    """Test connection to AIOStreams server."""
    base_url = get_base_url()

    if not base_url:
        xbmcgui.Dialog().ok('AIOStreams', 'Please set AIOStreams Base URL in settings first')
        return

    try:
        import time
        start_time = time.time()
        manifest = get_manifest()
        elapsed = time.time() - start_time

        if manifest:
            xbmcgui.Dialog().ok('AIOStreams Connection Test',
                               f'✓ Connection successful!\n\n'
                               f'Server: {base_url}\n'
                               f'Response time: {elapsed:.2f}s\n'
                               f'Catalogs available: {len(manifest.get("catalogs", []))}')
        else:
            xbmcgui.Dialog().ok('AIOStreams Connection Test',
                               f'✗ Connection failed\n\n'
                               f'Server: {base_url}\n'
                               f'Please check your settings and try again.')
    except Exception as e:
        xbmc.log(f'[AIOStreams] Connection test failed: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('AIOStreams Connection Test',
                           f'✗ Connection failed\n\n'
                           f'Error: {str(e)}\n\n'
                           f'Please check your settings and try again.')


def configure_aiostreams_action():
    """Open browser to configure AIOStreams and capture the manifest URL."""
    try:
        from resources.lib.web_config import configure_aiostreams
        result = configure_aiostreams()
        if result:
            xbmc.log(f'[AIOStreams] Configuration completed: {result}', xbmc.LOGINFO)
    except ImportError as e:
        xbmc.log(f'[AIOStreams] Failed to import web_config: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('AIOStreams', 'Web configuration module not available.\n\nPlease update the addon.')
    except Exception as e:
        xbmc.log(f'[AIOStreams] Configure action failed: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('AIOStreams', f'Configuration failed:\n\n{str(e)}')


def retrieve_manifest_action():
    """Retrieve manifest URL using UUID and password authentication."""
    try:
        from resources.lib.web_config import retrieve_manifest
        result = retrieve_manifest()
        if result:
            xbmc.log(f'[AIOStreams] Manifest retrieved: {result}', xbmc.LOGINFO)
    except ImportError as e:
        xbmc.log(f'[AIOStreams] Failed to import web_config: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('AIOStreams', 'Web configuration module not available.\n\nPlease update the addon.')
    except Exception as e:
        xbmc.log(f'[AIOStreams] Retrieve manifest action failed: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('AIOStreams', f'Retrieve manifest failed:\n\n{str(e)}')

# Widget cache: {cache_key: {'data': catalog_data, 'timestamp': time.time()}}
_widget_cache = {}
_widget_cache_ttl = 3600  # 1 hour in seconds (increased from 15 minutes)

def _get_cached_widget(cache_key):
    """Get cached widget data if still valid."""
    import time
    if cache_key in _widget_cache:
        cache_entry = _widget_cache[cache_key]
        age = time.time() - cache_entry['timestamp']
        if age < _widget_cache_ttl:
            xbmc.log(f'[AIOStreams] Widget cache hit: {cache_key} (age: {int(age)}s)', xbmc.LOGDEBUG)
            return cache_entry['data']
        else:
            # Expired, remove it
            del _widget_cache[cache_key]
            xbmc.log(f'[AIOStreams] Widget cache expired: {cache_key}', xbmc.LOGDEBUG)
    return None

def _cache_widget(cache_key, data):
    """Cache widget data."""
    import time
    _widget_cache[cache_key] = {'data': data, 'timestamp': time.time()}
    xbmc.log(f'[AIOStreams] Widget cached: {cache_key}', xbmc.LOGDEBUG)

def _clear_trakt_widget_cache():
    """
    Clear widget cache for Trakt-related widgets only.
    Called after Trakt actions (mark watched, add/remove watchlist).

    Clears cache for:
    - Trakt Next Up (home widget)
    - Trakt Watchlist Movies (home widget)
    - Trakt Watchlist Series (home widget)
    - Any catalog-based Trakt widgets (trending, popular, recommendations)
    """
    global _widget_cache

    # Clear catalog-based Trakt widgets (those with 'trakt' in the catalog ID)
    trakt_keys = [k for k in _widget_cache.keys() if 'trakt' in k.lower()]

    for key in trakt_keys:
        del _widget_cache[key]
        xbmc.log(f'[AIOStreams] Cleared Trakt widget cache: {key}', xbmc.LOGDEBUG)

    if trakt_keys:
        xbmc.log(f'[AIOStreams] Cleared {len(trakt_keys)} Trakt widget cache entries', xbmc.LOGINFO)

def smart_widget():
    """
    Dynamic widget content generator using widget_config.json.

    URL Parameters:
        index: Widget index (0, 1, 2, ...)
        content_type: 'series', 'movie', or 'home'

    Returns:
        Content from configured widget at specified index
    """
    from resources.lib import trakt
    # Suppression guard (Global or Internal)
    win_home = xbmcgui.Window(10000)
    if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
       win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
        xbmc.log('[AIOStreams] Suppression: smart_widget skipped (Search Active)', xbmc.LOGDEBUG)
        # Return TRUE but empty to prevent Kodi from showing "Plugin Error" dialog
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    
    index = int(params.get('index', 0))
    content_type = params.get('content_type', 'movie')

    # Optimization: If Search Dialog (1112) or Info Dialog (12003) OR ANY MODAL is open, skip background widget loading
    # DISABLE OPTIMIZATION TEMPORARILY FOR DEBUGGING
    # if xbmc.getCondVisibility('Window.IsVisible(1112)') or xbmc.getCondVisibility('Window.IsVisible(12003)') or xbmc.getCondVisibility('System.HasModalDialog'):
    #     xbmc.log(f'[AIOStreams] smart_widget: Skipping background load (Dialog Open) - index={index}', xbmc.LOGDEBUG)
    #     xbmcplugin.endOfDirectory(HANDLE)
    #     return

    xbmc.log(f'[AIOStreams] smart_widget: index={index}, content_type={content_type}', xbmc.LOGDEBUG)
    
    # Use widget_config_loader to get configured widget
    try:
        from resources.lib.widget_config_loader import get_widget_at_index
        
        # Map content_type to page name
        page_map = {'home': 'home', 'series': 'tvshows', 'movie': 'movies'}
        page = page_map.get(content_type, content_type)
        
        # Get widget from config
        widget = get_widget_at_index(page, index)

        if not widget:
            xbmc.log(f'[AIOStreams] smart_widget: No widget configured at index {index} for {page}', xbmc.LOGDEBUG)
            xbmcplugin.endOfDirectory(HANDLE)
            return
        
        # Extract widget details
        path = widget.get('path', '')
        label = widget.get('label', 'Unknown')
        
        xbmc.log(f'[AIOStreams] smart_widget: Loading index {index} for {page}: "{label}" (Path: {path})', xbmc.LOGDEBUG)

        # Define property name for the header
        prop_name = None
        if page == 'home':
            prop_name = f'WidgetLabel_Home_{index}'
        elif page == 'movies':
            prop_name = f'movie_catalog_{index}_name'
        elif page == 'tvshows':
            prop_name = f'series_catalog_{index}_name'

        if prop_name:
            xbmcgui.Window(10000).setProperty(prop_name, label)
            # Set generic property too
            xbmcgui.Window(10000).setProperty(f'{page}_widget_{index}_name', label)
        
        # Parse the widget path
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(path)
        widget_params = parse_qs(parsed.query)
        
        # Extract action
        action = widget_params.get('action', [None])[0]
        
        if not action:
            xbmc.log(f'[AIOStreams] smart_widget: No action in widget path', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(HANDLE)
            return
        
        # Handle different actions
        # Handle different actions
        if action == 'trakt_next_up':
            xbmc.log(f'[AIOStreams] smart_widget: Executing trakt_next_up', xbmc.LOGDEBUG)
            return trakt_next_up()
        
        elif action == 'trakt_watchlist':
            media_type = widget_params.get('media_type', ['movies'])[0]
            xbmc.log(f'[AIOStreams] smart_widget: Executing trakt_watchlist ({media_type})', xbmc.LOGDEBUG)
            return trakt_watchlist({'media_type': media_type})
        
        elif action == 'catalog' or action == 'browse_catalog':
            catalog_id = widget_params.get('catalog_id', [None])[0]
            
            # LOCAL OVERRIDE: Redirect Trakt recommendations to local API - REMOVED PER REQUEST
            # if catalog_id and 'trakt.recommendations' in catalog_id:
            #     xbmc.log(f'[AIOStreams] smart_widget: Overriding {catalog_id} with local Trakt recommendations', xbmc.LOGDEBUG)
            #     media_type = 'movies' if 'movies' in catalog_id else 'shows'
            #     return trakt_recommendations({'media_type': media_type, 'page': 'home', 'index': str(index)})
            catalog_id = widget_params.get('catalog_id', [None])[0]
            
            try:
                with open('/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/smart_widget_debug.txt', 'a') as f:
                    f.write(f"Action: {action}, Catalog ID: {catalog_id}\n")
            except: pass

            if not catalog_id:
                xbmc.log(f'[AIOStreams] smart_widget: missing catalog_id for {action}', xbmc.LOGERROR)
                xbmcplugin.endOfDirectory(HANDLE)
                return
            
            xbmc.log(f'[AIOStreams] smart_widget: Executing catalog/browse_catalog {catalog_id}', xbmc.LOGDEBUG)
            xbmcplugin.setPluginCategory(HANDLE, label)
            xbmcplugin.setContent(HANDLE, 'tvshows' if content_type == 'series' else 'movies')
            
            if HAS_MODULES:
                trakt.prime_database_cache(content_type)
            
            cache_key = f'widget_{content_type}_{catalog_id}_all'
            catalog_data = _get_cached_widget(cache_key)
            
            if catalog_data is None:
                try:
                    with open('/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/smart_widget_debug.txt', 'a') as f:
                        f.write(f"Fetching catalog data from source...\n")
                except: pass
                
                import time
                start_time = time.time()
                catalog_data = get_catalog(content_type, catalog_id, genre=None, skip=0)
                duration = time.time() - start_time
                xbmc.log(f'[AIOStreams] smart_widget: get_catalog took {duration:.2f} seconds for {catalog_id}', xbmc.LOGDEBUG)

                if catalog_data and 'metas' in catalog_data:
                    _cache_widget(cache_key, catalog_data)
            
            try:
                with open('/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/smart_widget_debug.txt', 'a') as f:
                    has_data = catalog_data is not None
                    has_metas = 'metas' in catalog_data if has_data else False
                    meta_count = len(catalog_data['metas']) if has_metas else 0
                    f.write(f"Data retrieved: {has_data}, Has Metas: {has_metas}, Count: {meta_count}\n")
            except: pass

            if not catalog_data or 'metas' not in catalog_data:
                xbmc.log(f'[AIOStreams] smart_widget: No data found for catalog {catalog_id}', xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(HANDLE)
                return
            
            # Pre-fetch full metadata in parallel to get clearlogos
            items_to_fetch = []
            for meta in catalog_data['metas']:
                item_id = meta.get('id')
                if item_id:
                    items_to_fetch.append({'ids': {'imdb': item_id}})
            
            # Fetch metadata with logos in parallel
            metadata_map = {}
            if items_to_fetch:
                xbmc.log(f'[AIOStreams] smart_widget: Fetching {len(items_to_fetch)} items metadata in parallel...', xbmc.LOGDEBUG)
                metadata_map = fetch_metadata_parallel(items_to_fetch, content_type)

            for meta in catalog_data['metas']:
                try:
                    item_id = meta.get('id')
                    if not item_id:
                        continue
                    
                    # Merge with full metadata if available (for logos, cast, etc.)
                    full_meta = metadata_map.get(item_id, {})
                    if full_meta:
                        # Merge: full_meta provides detailed info, catalog meta provides basics
                        merged_meta = {**meta, **full_meta.get('meta', {})}
                        # Ensure logo from full metadata is used
                        if full_meta.get('meta', {}).get('logo'):
                            merged_meta['logo'] = full_meta['meta']['logo']
                    else:
                        merged_meta = meta
                    
                    if content_type == 'series':
                        url = get_url(action='show_seasons', meta_id=item_id)
                        is_folder = True
                    else:
                        url = get_url(action='show_streams', content_type='movie', media_id=item_id,
                                    title=merged_meta.get('name', ''), poster=merged_meta.get('poster', ''),
                                    fanart=merged_meta.get('background', ''), clearlogo=merged_meta.get('logo', ''))
                        is_folder = False
                    
                    list_item = create_listitem_with_context(merged_meta, content_type, url)
                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)
                except Exception as e:
                    import traceback
                    xbmc.log(f'[AIOStreams] smart_widget: Failed to add item: {e}', xbmc.LOGDEBUG)
                    continue
            # Set NumItems property for the skin
            count_prop = f"AIOStreams.{page}.{index}.NumItems"
            item_count = len(catalog_data["metas"])
            xbmcgui.Window(10000).setProperty(count_prop, str(item_count))
            xbmc.log(f"[AIOStreams] smart_widget: Set {count_prop} = {item_count}", xbmc.LOGDEBUG)

            
            xbmcplugin.endOfDirectory(HANDLE)
            return
        
        else:
            xbmc.log(f'[AIOStreams] smart_widget: Unknown action "{action}"', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(HANDLE)
            return
    
    except Exception as e:
        xbmc.log(f'[AIOStreams] smart_widget: Error: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE)
def configured_widget():
    """
    Dynamic widget content from widget_config.json

    URL Parameters:
        index: Widget index (0, 1, 2, ...)
        page: 'home', 'tvshows', or 'movies'

    Returns:
        Widget content based on configuration
    """
    from resources.lib.widget_config_loader import get_widget_at_index

    params = dict(parse_qsl(sys.argv[2][1:]))
    index = int(params.get('index', 0))
    page = params.get('page', 'home')

    # Optimization: If Search Dialog (1112) or Info Dialog (12003) OR ANY MODAL is open, skip background widget loading
    if xbmc.getCondVisibility('Window.IsVisible(1112)') or xbmc.getCondVisibility('Window.IsVisible(12003)') or xbmc.getCondVisibility('System.HasModalDialog'):
        xbmc.log(f'[AIOStreams] configured_widget: Skipping background load (Dialog Open) - index={index}', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmc.log(f'[AIOStreams] configured_widget: index={index}, page={page}', xbmc.LOGINFO)

    # Get the configured widget
    widget = get_widget_at_index(page, index)

    if not widget:
        xbmc.log(f'[AIOStreams] configured_widget: No widget configured at index {index} for {page}', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Extract widget details
    label = widget.get('label', 'Unknown')
    path = widget.get('path', '')
    widget_type = widget.get('type', 'unknown')
    is_trakt = widget.get('is_trakt', False)

    xbmc.log(f'[AIOStreams] configured_widget: Loading "{label}" (type: {widget_type}, is_trakt: {is_trakt})', xbmc.LOGINFO)

    # Parse the widget path to extract action and parameters
    try:
        if '?' in path:
            path_parts = path.split('?')
            query_string = path_parts[1] if len(path_parts) > 1 else ''
            widget_params = dict(parse_qsl(query_string))
            action = widget_params.get('action', '')

            xbmc.log(f'[AIOStreams] configured_widget: Redirecting to action "{action}" with params {widget_params}', xbmc.LOGDEBUG)

            # Route to the appropriate action
            if action == 'trakt_next_up':
                return trakt_next_up()
            elif action == 'trakt_watchlist':
                media_type = widget_params.get('media_type', 'movies')
                return trakt_watchlist({'media_type': media_type})
            elif action == 'browse_catalog':
                # Browse a specific catalog
                catalog_id = widget_params.get('catalog_id', '')
                content_type = widget_params.get('content_type', 'movie')
                catalog_name = widget_params.get('catalog_name', label)

                # Set the window property for the header
                try:
                    xbmcgui.Window(10000).setProperty(f'{page}_widget_{index}_name', catalog_name)
                except:
                    pass

                # Fetch catalog content
                catalog_data = get_catalog(content_type, catalog_id, genre=None, skip=0)

                if not catalog_data or 'metas' not in catalog_data:
                    xbmc.log(f'[AIOStreams] configured_widget: No content in catalog {catalog_id}', xbmc.LOGWARNING)
                    xbmcplugin.endOfDirectory(HANDLE)
                    return

                # Set plugin metadata
                xbmcplugin.setPluginCategory(HANDLE, catalog_name)
                xbmcplugin.setContent(HANDLE, 'tvshows' if content_type == 'series' else 'movies')

                # Add items
                for meta in catalog_data['metas']:
                    item_id = meta.get('id')
                    if not item_id:
                        continue

                    # For series: navigate to show
                    if content_type == 'series':
                        url = get_url(action='show_seasons', meta_id=item_id)
                        is_folder = True
                    else:
                        url = get_url(action='show_streams', content_type='movie', media_id=item_id,
                                     title=meta.get('name', ''), poster=meta.get('poster', ''),
                                     fanart=meta.get('background', ''), clearlogo=meta.get('logo', ''))
                        is_folder = False

                    list_item = create_listitem_with_context(meta, content_type, url)
                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

                xbmcplugin.endOfDirectory(HANDLE)
                return
            else:
                xbmc.log(f'[AIOStreams] configured_widget: Unknown action "{action}"', xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(HANDLE)
                return
        else:
            xbmc.log(f'[AIOStreams] configured_widget: Invalid widget path "{path}"', xbmc.LOGERROR)
            xbmcplugin.endOfDirectory(HANDLE)
            return
    except Exception as e:
        xbmc.log(f'[AIOStreams] configured_widget: Error processing widget: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return


# ============================================================================
# Action Registry - Cleaner routing using dictionary pattern
# ============================================================================

# Action handler registry - maps action names to handler functions
def play_next(params):
    """
    Handle play_next request (e.g. from UpNext).
    This just wraps the standard play logic but ensures we pass explicit params.
    """
    xbmc.log(f'[AIOStreams] ===== PLAY_NEXT INVOKED =====', xbmc.LOGINFO)
    xbmc.log(f'[AIOStreams] play_next params: {params}', xbmc.LOGINFO)
    xbmc.log(f'[AIOStreams] HANDLE value: {HANDLE}', xbmc.LOGINFO)
    
    if not HAS_MODULES:
        xbmc.log(f'[AIOStreams] play_next: HAS_MODULES is False, aborting', xbmc.LOGWARNING)
        return
    
    # Call play() directly with the extracted params
    xbmc.log(f'[AIOStreams] play_next: Calling play() with params', xbmc.LOGINFO)
    try:
        play(params)
    except Exception as e:
        xbmc.log(f'[AIOStreams] play_next error: {e}', xbmc.LOGERROR)
    xbmc.log(f'[AIOStreams] play_next: play() completed', xbmc.LOGINFO)



def action_info(params):
    """Handle info action."""
    meta_id = params.get('id') or params.get('imdb_id')
    content_type = params.get('content_type', 'movie')
    
    if not meta_id:
        xbmc.log('[AIOStreams] action_info: No ID provided', xbmc.LOGERROR)
        return

    xbmc.log(f'[AIOStreams] Fetching info for {content_type}/{meta_id}', xbmc.LOGINFO)
    
    # Clear stale properties first to avoid flash of old content
    clear_window_properties(['InfoWindow.Title', 'InfoWindow.Plot', 'InfoWindow.Director', 
                           'InfoWindow.Writer', 'InfoWindow.Cast', 'InfoWindow.Duration', 
                           'InfoWindow.Year', 'InfoWindow.Genre', 'InfoWindow.Rating', 
                           'InfoWindow.Votes', 'InfoWindow.Trailer', 'InfoWindow.IsCustom'])
    
    # Show busy dialog while fetching
    xbmc.executebuiltin('ActivateWindow(busydialog)')
    
    try:
        # Fetch metadata
        meta = get_meta(content_type, meta_id)
        
        if not meta:
            xbmc.executebuiltin('Dialog.Close(busydialog)')
            xbmcgui.Dialog().notification('AIOStreams', 'Metadata not found', xbmcgui.NOTIFICATION_ERROR)
            return

        # Create list item with full context
        # We need a dummy URL since we aren't playing it immediately, but it might be used for Play button in dialog
        play_url = get_url(action='play', content_type=content_type, imdb_id=meta_id)
        list_item = create_listitem_with_context(meta, content_type, play_url)
        
        # Close busy dialog
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        
        # Open Info Dialog
        # Note: We can't easily "push" a List Item to the standard DialogVideoInfo.
        # However, we can use the 'open_info_dialog' helper pattern if available, or extended script.
        # But a trick is to open a hidden directory containing this item and trigger Info? No.
        
        # Best approach for skin integration:
        # 1. Set Window Properties (which the skin uses for Cast, etc.)
        # Open Info Dialog explicitly to ensure it opens with new properties
        # We use ID 12003 which is the standard id for MovieInformation
        xbmc.executebuiltin('ActivateWindow(12003)')
        
        # If the user wants a full "scrape", we might need to update the focused item?
        # That's hard from here.
        
        # Alternative: Use script.extendedinfo if available?
        # xbmc.executebuiltin(f'RunScript(script.extendedinfo,info=extendedinfo,dbid={meta_id})') # if library?
        
        # Let's rely on standard Kodi behavior: 
        # If we have the metadata, maybe we can just show a custom notification or assume the skin reads properties?
        # The user said "calling for info ... should scrape and give me the information".
        
        # Let's try populating Window(Home) properties with EVERYTHING, just like we did for Cast.
        # If the skin's DialogVideoInfo.xml uses $INFO[ListItem.Title], it uses the focused item.
        # We cannot easily change the focused item's data on the fly.
        
        # However, we can use xbmcgui.Dialog().info(list_item) IF it existed. 
        # Since it doesn't, we can try OpenInfo script format.
        
        # Let's populate Window Properties and hope the skin uses them or we modify the skin to key off a "ScrapedInfo" property.
        # Actually, let's look at DialogVideoInfo.xml again. It uses $INFO[ListItem.Thumb], etc.
        
        # If we cannot update the ListItem, we are stuck unless we open a *different* window or reload the container.
        # Refreshing the container with new data is too slow/disruptive.
        
        # Proxy solution: Open a temporary playlist? No.
        
        # Let's assume the user is okay with us setting Properties and they might edit the skin to read them 
        # OR (better) we modify the skin to use a variable: $VAR[InfoTitle] which checks Window Property first.
        
        # But wait, checking the code for Cast Refactor:
        # We used $INFO[Window(Home).Property(InfoWindow.Cast.X.Name)]
        # So using Window Properties is established pattern here!
        
        # Let's set standard InfoWindow properties
        window = xbmcgui.Window(10000)
        window.setProperty('InfoWindow.IsCustom', 'true')
        window.setProperty('InfoWindow.IMDB', meta_id)
        window.setProperty('InfoWindow.Title', meta.get('name', ''))
        window.setProperty('InfoWindow.Plot', meta.get('description', ''))
        window.setProperty('InfoWindow.Year', str(meta.get('year', '')))
        window.setProperty('InfoWindow.Director', meta.get('director', ''))
        window.setProperty('InfoWindow.Premiered', meta.get('released', '').split('T')[0])
        window.setProperty('InfoWindow.DBType', content_type)
        window.setProperty('InfoWindow.Poster', meta.get('poster', ''))
        window.setProperty('InfoWindow.Fanart', meta.get('background', ''))
        
        # Duration handling
        try:
            runtime = meta.get('runtime', 0)
            if isinstance(runtime, int):
                window.setProperty('InfoWindow.Duration', str(runtime))
            else:
                 window.setProperty('InfoWindow.Duration', str(runtime).replace('min', '').strip())
        except:
            pass

        # Now open the dialog.
        # Short sleep to ensure properties are propagated
        xbmc.sleep(200)
        xbmc.executebuiltin('ActivateWindow(12003)') # DialogVideoInfo
        
    except Exception as e:
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.log(f'[AIOStreams] action_info error: {e}', xbmc.LOGERROR)
    else:
        # If it returns False or None (though implementation returns None currently, let's assume success if no error logged)
        # Actually clear_clearlogo_cache() from line 235 logs but doesn't return value explicitly (returns None)
        # So check the logic.
        xbmcgui.Dialog().notification("AIOStreams", "Clearlogo cache cleared", xbmcgui.NOTIFICATION_INFO, 3000)

def update_container():
    """Handle container update request from skin."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    target_id = params.get('target_id')
    meta_id = params.get('meta_id')
    season = params.get('season')
    
    xbmc.log(f'[AIOStreams] update_container triggered: target={target_id}, meta={meta_id}, season={season}', xbmc.LOGINFO)
    
    if target_id and meta_id and season:
        url = get_url(action='show_episodes', meta_id=meta_id, season=season)
        
        # KEY FIX: Store complex URL in a window property to avoid parser issues
        # The executebuiltin command will reference the property, skipping the parser's limitations
        window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        window.setProperty('AIOStreams_EpisodeUpdate_URL', url)
        
        # Execute update using the property reference
        # NOTE: We use $INFO[...] inside the string. Kodi expands this BEFORE executing the command?
        # Actually, Container.Update takes a string path.
        # We need to ensure Kodi expands the property.
        # Using $INFO in executebuiltin usually works.
        xbmc.log(f'[AIOStreams] Setting Update Property: {url}', xbmc.LOGINFO)
        # Use single quotes around the property reference to satisfy the parser
        xbmc.executebuiltin(f"Container({target_id}).Update('$INFO[Window.Property(AIOStreams_EpisodeUpdate_URL)]')")



ACTION_REGISTRY = {
    # Index/Home
    'index': lambda p: index(),
    'search': lambda p: search(),
    'search_tab': lambda p: handle_search_tab(p),
    'clear_cache': lambda p: clear_cache(),
    
    # Browse actions
    'movie_lists': lambda p: movie_lists(),
    'series_lists': lambda p: series_lists(),
    'catalogs': lambda p: list_catalogs(),
    'smart_widget': lambda p: smart_widget(),
    'configured_widget': lambda p: configured_widget(),
    'catalog_genres': lambda p: list_catalog_genres(),
    'browse_catalog': lambda p: browse_catalog(),

    # TV Show navigation
    'show_seasons': lambda p: show_seasons(),
    'browse_show': lambda p: browse_show(),
    'show_episodes': lambda p: show_episodes(),
    'show_related': lambda p: show_related(),
    'update_container': lambda p: update_container(),

    # Trakt menu actions
    'trakt_menu': lambda p: trakt_menu(),
    'trakt_watchlist': lambda p: trakt_watchlist(),
    'trakt_collection': lambda p: None, # Removed
    'trakt_recommendations': lambda p: None, # Removed
    'trakt_next_up': lambda p: trakt_next_up(),

    # Trakt authentication
    'trakt_auth': lambda p: trakt_auth(),
    'trakt_revoke': lambda p: trakt_revoke(),

    # Trakt item actions
    'trakt_add_watchlist': lambda p: trakt_add_watchlist(),
    'trakt_remove_watchlist': lambda p: trakt_remove_watchlist(),
    'trakt_mark_watched': lambda p: trakt_mark_watched(),
    'trakt_mark_unwatched': lambda p: trakt_mark_unwatched(),
    'trakt_remove_playback': lambda p: trakt_remove_playback(),
    'trakt_hide_show': lambda p: trakt_hide_show(),
    'trakt_hide_from_progress': lambda p: trakt_hide_from_progress(),
    'trakt_unhide_from_progress': lambda p: trakt_unhide_from_progress(),

    # Settings/maintenance actions
    'clear_stream_stats': lambda p: clear_stream_stats(),
    'clear_preferences': lambda p: clear_preferences(),
    'database_reset': lambda p: database_reset(),
    'clear_trakt_cache': lambda p: clear_trakt_cache(),
    'show_database_info': lambda p: show_database_info(),
    'test_connection': lambda p: test_connection(),
    'quick_actions': lambda p: quick_actions(),
    'configure_aiostreams': lambda p: configure_aiostreams_action(),
    'retrieve_manifest': lambda p: retrieve_manifest_action(),
    'refresh_manifest_cache': lambda p: refresh_manifest_cache(),
    'get_all_catalogs': lambda p: get_all_catalogs_action(),
    'get_folder_browser_catalogs': lambda p: get_folder_browser_catalogs_action(),
    'open_youtube_folder': lambda p: open_youtube_folder(p),
    'info': lambda p: action_info(p),
    'youtube_menu': lambda p: youtube_menu(),
    
    # Playback actions
    'play': lambda p: play(p),
    'play_next': lambda p: play_next(p),
    'play_next_source': lambda p: play_next_source(p),
    'play_first': lambda p: play_first(),
    'select_stream': lambda p: select_stream(),
    'show_streams': lambda p: show_streams(),
}


def open_youtube_folder(params):
    """Close search dialog and open YouTube folder in video window."""
    url = params.get('url', '')
    if url:
        xbmc.log(f'[AIOStreams] Opening YouTube folder: {url}', xbmc.LOGINFO)
        
        # Robustly close the custom search window (ID 1112)
        # We try multiple methods to ensure it's gone
        xbmc.executebuiltin('Dialog.Close(1112, true)')
        xbmc.executebuiltin('Window.Close(1112, true)')
        
        # Even more aggressive closure for window 1112
        xbmc.executebuiltin('Action(CloseDialog, 1112)')
        
        # Larger delay to let skin settle before switching windows
        xbmc.sleep(600)
        
        # Open the YouTube folder in the video window (without 'return' to see if it helps)
        xbmc.executebuiltin(f'ActivateWindow(Videos, "{url}")')


def handle_search_tab(params):
    """Handle search_tab action with pagination logic."""
    query = params.get('query', '')
    content_type = params.get('content_type', 'movie')
    skip = int(params.get('skip', 0))
    is_widget = params.get('widget') == 'true'

    if not query:
        keyboard = xbmcgui.Dialog().input('Search', type=xbmcgui.INPUT_ALPHANUM)
        if keyboard:
            query = keyboard
        else:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return

    if skip > 0:
        # Handle pagination
        xbmcplugin.setPluginCategory(HANDLE, f'Search {content_type.title()}: {query}')
        xbmcplugin.setContent(HANDLE, 'movies' if content_type == 'movie' else 'tvshows')

        if not is_widget:
            # Add navigation tabs even on paginated results
            add_tab_switcher(query, content_type)

        results = search_catalog(query, content_type, skip=skip)
        if results and 'metas' in results:
            items = results['metas']
            if HAS_MODULES and filters:
                items = filters.filter_items(items)

            for meta in items:
                item_id = meta.get('id')
                if content_type == 'series':
                    url = get_url(action='show_seasons', meta_id=item_id)
                    is_folder = True
                else:
                    title = meta.get('name', 'Unknown')
                    poster = meta.get('poster', '')
                    fanart = meta.get('background', '')
                    clearlogo = meta.get('logo', '')
                    url = get_url(action='play', content_type='movie', imdb_id=item_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
                    is_folder = False
                list_item = create_listitem_with_context(meta, content_type, url)

                # Set IsPlayable property for movies
                if not is_folder:
                    list_item.setProperty('IsPlayable', 'true')

                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

            # Check for next page (heuristic check)
            if items and len(items) >= 20:
                list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
                next_skip = skip + 20
                url = get_url(action='search_tab', content_type=content_type, query=query, skip=next_skip)
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
    else:
        # Initial search - show with tabs
        search_by_tab(query, content_type, is_widget=is_widget)


def router(params):
    """
    Route to the appropriate function based on parameters.
    Uses action registry pattern for cleaner, more maintainable code.
    """
    action_name = params.get('action', '')
    
    # If no action but query exists, assume search
    if not action_name and ('search' in params or 'query' in params or 'q' in params):
        action_name = 'search'
        if 'search' in params and not params.get('query'):
            params['query'] = params['search']
        elif 'q' in params and not params.get('query'):
            params['query'] = params['q']

    # Look up action in registry
    handler = ACTION_REGISTRY.get(action_name)

    if handler:
        # Execute registered handler
        xbmc.log(f'[AIOStreams] Dispatching action: {action_name}', xbmc.LOGDEBUG)
        try:
            handler(params)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Action error ({action_name}): {e}', xbmc.LOGERROR)
    elif action_name:
        # Unknown action with a name - log warning and show index
        xbmc.log(f'[AIOStreams] Unknown action: {action_name}', xbmc.LOGWARNING)
        index()
    else:
        # No action specified - show index
        index()


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    xbmc.log(f'[AIOStreams] ===== PLUGIN INVOKED =====', xbmc.LOGDEBUG)
    xbmc.log(f'[AIOStreams] sys.argv: {sys.argv}', xbmc.LOGDEBUG)
    
    arg_raw = sys.argv[2]
    if arg_raw.startswith('?'):
        params = dict(parse_qsl(arg_raw[1:]))
    elif '/' in arg_raw:
        # Handle "Clean Paths" for Kodi parser stability
        # Format: /action/id/season or /action/id
        parts = [p for p in arg_raw.split('/') if p]
        params = {}
        if len(parts) >= 1:
            params['action'] = parts[0]
        if len(parts) >= 2:
            params['meta_id'] = parts[1]
        if len(parts) >= 3:
            params['season'] = parts[2]
        xbmc.log(f'[AIOStreams] Clean Path parsed: {params}', xbmc.LOGDEBUG)
    else:
        params = {}
        
    xbmc.log(f'[AIOStreams] Parsed params: {params}', xbmc.LOGDEBUG)
    xbmc.log(f'[AIOStreams] Action: {params.get("action", "<none>")}', xbmc.LOGDEBUG)
    router(params)
    xbmc.log(f'[AIOStreams] ===== PLUGIN EXECUTION COMPLETE =====', xbmc.LOGDEBUG)

    # Cleanup on exit if using new modules
    if HAS_NEW_MODULES:
        try:
            g.deinit()
        except:
            pass

