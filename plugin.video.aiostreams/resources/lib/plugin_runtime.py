"""Plugin-bound API, cache, and metadata helpers."""
import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib import cache, settings_helpers, streams
from resources.lib.aiostreams_client import AIOStreamsClient, AIOStreamsClientError
from resources.lib.media import MediaRef
from resources.lib.safe_logging import redact_identifier
from resources.lib.stream_utils import normalize_streams
from resources.lib.clearlogo import get_cached_clearlogo_path, download_and_cache_clearlogo


ADDON = None
HANDLE = -1
HAS_MODULES = False
_aiostreams_client = None
_aiostreams_client_config = None


def configure(addon, handle, has_modules):
    """Bind this lightweight helper module to the current plugin invocation."""
    global ADDON, HANDLE, HAS_MODULES, _aiostreams_client, _aiostreams_client_config
    ADDON = addon
    HANDLE = handle
    HAS_MODULES = has_modules
    _aiostreams_client = None
    _aiostreams_client_config = None


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


def get_aiostreams_client():
    """Return the one client for the current add-on configuration."""
    global _aiostreams_client, _aiostreams_client_config
    base_url = get_base_url()
    config = (base_url, get_timeout(), ADDON.getAddonInfo('version'))
    if _aiostreams_client is not None and _aiostreams_client_config == config:
        return _aiostreams_client

    sql_cache = None
    if HAS_MODULES:
        try:
            from resources.lib import trakt
            sql_cache = trakt.get_trakt_db()
        except Exception:
            pass
    _aiostreams_client = AIOStreamsClient(
        base_url, timeout=config[1], addon_version=config[2], sql_cache=sql_cache
    )
    _aiostreams_client_config = config
    return _aiostreams_client


def request_aiostreams(operation, error_message, request):
    """Translate client failures at the Kodi action boundary."""
    try:
        return request()
    except AIOStreamsClientError as error:
        xbmc.log(f'[AIOStreams] {operation} failed: {type(error).__name__}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', error_message, xbmcgui.NOTIFICATION_ERROR)
        return None


def get_all_catalogs_action(params=None):
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


def get_folder_browser_catalogs_action(params=None):
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


def get_manifest(force=False):
    """Fetch the configured manifest through the shared API client."""
    if not get_base_url():
        return None
    return request_aiostreams(
        'manifest', 'Error fetching manifest',
        lambda: get_aiostreams_client().get_manifest(force=force),
    )


def get_search_catalog_id(content_type):
    """Dynamically find the search catalog ID for a given content type."""
    manifest = get_manifest()
    if not manifest:
        return '39fe3b0.search'  # Fallback

    # Mapping for content types
    m_type_map = {
        'movies': 'movie',
        'tvshows': 'series',
        'tvshow': 'series',
        'series': 'series'
    }
    m_type = m_type_map.get(content_type, content_type)

    # Try to find a catalog of the requested type with "search" in its extras
    for catalog in manifest.get('catalogs', []):
        if catalog.get('type') == m_type:
            extras = catalog.get('extra', [])
            for extra in extras:
                if isinstance(extra, dict) and extra.get('name') == 'search':
                    xbmc.log(f'[AIOStreams] Found search catalog for {content_type} ({m_type}): {catalog.get("id")} ({catalog.get("name")})', xbmc.LOGDEBUG)
                    return catalog.get('id')

    # Secondary attempt: Look for ANY catalog with "search" in name or ID if type matches
    for catalog in manifest.get('catalogs', []):
        if catalog.get('type') == m_type:
            cat_id = catalog.get('id', '').lower()
            cat_name = catalog.get('name', '').lower()
            if 'search' in cat_id or 'search' in cat_name:
                return catalog.get('id')

    # Fallback to the common ID
    return '39fe3b0.search'


def search_catalog(query, content_type='movie', skip=0):
    """Search the AIOStreams catalog with pagination."""
    if content_type in ['video', 'youtube'] or 'youtube' in str(content_type):
        youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
        if not youtube_available:
            xbmc.log(f'[AIOStreams] Blocking YouTube search request for "{query}"', xbmc.LOGINFO)
            return {'metas': []}

    # Mapping for content types to match manifest expectations
    m_type_map = {
        'movies': 'movie',
        'tvshows': 'series',
        'tvshow': 'series',
        'series': 'series'
    }
    m_type = m_type_map.get(content_type, content_type)
    catalog_id = get_search_catalog_id(m_type)
    return request_aiostreams(
        'search', 'Search error',
        lambda: get_aiostreams_client().search(query, m_type, catalog_id, skip),
    )


def get_streams(content_type, media_id):
    """Fetch streams for a given media ID."""
    result = request_aiostreams(
        'streams', 'Stream error',
        lambda: get_aiostreams_client().get_streams(content_type, media_id),
    )
    if result:
        normalized = normalize_streams(result.get('streams', []))
        result['streams'] = normalized['playable']
        result['_stream_summary'] = normalized
        counts = ', '.join(f'{kind}={count}' for kind, count in sorted(normalized['counts'].items())) or 'none'
        xbmc.log(
            f'[AIOStreams] Stream response: type={content_type}, id={media_id}, '
            f'total={sum(normalized["counts"].values())}, playable={len(normalized["playable"])}, '
            f'transports=({counts})', xbmc.LOGINFO)
        settings_helpers.log_debug(f'Normalized stream response for type={content_type}, id={media_id}')
        for message in normalized['messages']:
            xbmc.log(f'[AIOStreams] Stream message: {message}', xbmc.LOGWARNING)
    return result


def show_no_playable_streams(stream_data, resolve=False):
    """Explain a direct-stream miss and fail an outstanding Kodi resolver."""
    summary = (stream_data or {}).get('_stream_summary', {})
    messages = summary.get('messages') or []
    counts = summary.get('counts') or {}
    unsupported = sum(count for kind, count in counts.items()
                      if kind not in ('direct_url', 'synthetic_error', 'synthetic_statistic'))
    message = messages[0] if messages else (
        f'No direct streams available ({unsupported} unsupported transport entries)' if unsupported
        else 'No direct streams available')
    xbmc.log(f'[AIOStreams] No playable streams: {message}', xbmc.LOGWARNING)
    xbmcgui.Dialog().notification('AIOStreams', message[:250], xbmcgui.NOTIFICATION_ERROR)
    if resolve and HANDLE >= 0:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def get_catalog(content_type, catalog_id, genre=None, skip=0):
    """Fetch a configuration-scoped catalog through the shared API client."""
    return request_aiostreams(
        'catalog', 'Catalog error',
        lambda: get_aiostreams_client().get_catalog(content_type, catalog_id, genre, skip),
    )


def get_subtitles(content_type, media_id):
    """Fetch subtitles for a given media ID."""
    return request_aiostreams(
        'subtitles', 'Subtitle error',
        lambda: get_aiostreams_client().get_subtitles(content_type, media_id),
    )


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


def get_meta(content_type, meta_id):
    """Fetch metadata through the shared client and retain clearlogo behavior."""
    if content_type in ['tvshow', 'tvshows', 'episode']:
        content_type = 'series'
    if content_type == 'home':
        content_type = 'movie'
    result = request_aiostreams(
        'metadata', 'Meta error',
        lambda: get_aiostreams_client().get_meta(content_type, meta_id),
    )
    if result:
        _ensure_clearlogo_cached(result, content_type, meta_id)
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
                xbmc.log(
                    f'[AIOStreams] Clearlogo missing for {redact_identifier(meta_id)}; downloading in background',
                    xbmc.LOGDEBUG,
                )
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
