import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
from urllib.parse import urlencode, parse_qsl
import requests
import json

# Import new modules
try:
    from resources.lib import trakt, filters, cache
    from resources.lib.monitor import PLAYER
    from resources.lib import streams, ui_helpers, settings_helpers, constants
    HAS_MODULES = True
except Exception as e:
    HAS_MODULES = False
    xbmc.log(f'[AIOStreams] Failed to import modules: {e}', xbmc.LOGERROR)

# Initialize addon
ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
HANDLE = int(sys.argv[1])


class StreamSelectDialog(xbmcgui.WindowXMLDialog):
    """Custom dialog for multi-line stream selection."""

    def __init__(self, *args, **kwargs):
        self.streams = kwargs.get("streams", [])
        self.selected_index = None
        self.title = kwargs.get("title", "Select Stream")

    def onInit(self):
        # Set dialog title
        self.setProperty("dialog_title", self.title)

        # Get the list control from XML
        try:
            list_control = self.getControl(1000)
            list_control.reset()

            # Add items with multi-line labels
            for stream_label in self.streams:
                list_item = xbmcgui.ListItem(label=stream_label)
                list_control.addItem(list_item)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error initializing stream dialog: {e}', xbmc.LOGERROR)

    def onClick(self, controlId):
        if controlId == 1000:  # List clicked
            try:
                list_control = self.getControl(1000)
                self.selected_index = list_control.getSelectedPosition()
                self.close()
            except Exception as e:
                xbmc.log(f'[AIOStreams] Error on list click: {e}', xbmc.LOGERROR)
        elif controlId == 2000:  # Cancel button
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.close()


# Run cache cleanup on startup (async, won't block)
if HAS_MODULES:
    try:
        cache.cleanup_expired_cache()
    except:
        pass
    
    # Run migration check on addon startup (once per install)
    try:
        from resources.lib.database.migration import DatabaseMigration
        migration = DatabaseMigration()
        if migration.is_migration_needed():
            xbmc.log('[AIOStreams] Running database migration on startup...', xbmc.LOGINFO)
            migration.migrate()
    except Exception as e:
        xbmc.log(f'[AIOStreams] Migration check failed: {e}', xbmc.LOGERROR)


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


def get_timeout():
    """Get request timeout from settings."""
    try:
        return int(get_setting('timeout', '10'))
    except ValueError:
        return 10


def get_url(**kwargs):
    """Create a URL for calling the plugin recursively from the given set of keyword arguments."""
    return '{}?{}'.format(sys.argv[0], urlencode(kwargs))


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
            xbmc.log(f'[AIOStreams] HTTP 304 Not Modified: Using cached data for {cache_key}', xbmc.LOGINFO)
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
    xbmc.log(f'[AIOStreams] Requesting streams from: {url}', xbmc.LOGINFO)
    result = make_request(url, 'Stream error')
    if result:
        xbmc.log(f'[AIOStreams] Received {len(result.get("streams", []))} streams for {media_id}', xbmc.LOGINFO)
    return result


def get_catalog(content_type, catalog_id, genre=None, skip=0):
    """Fetch a catalog from AIOStreams with 6-hour caching."""
    # Build cache identifier from all parameters
    cache_id = f"{content_type}:{catalog_id}:{genre or 'none'}:{skip}"

    # Check cache first (6 hours = 21600 seconds)
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

    xbmc.log(f'[AIOStreams] Requesting catalog from: {url}', xbmc.LOGINFO)
    catalog = make_request(url, 'Catalog error')

    # Cache the result
    if catalog and HAS_MODULES:
        cache.cache_data('catalog', cache_id, catalog)

    return catalog


def get_subtitles(content_type, media_id):
    """Fetch subtitles for a given media ID."""
    base_url = get_base_url()
    url = f"{base_url}/subtitles/{content_type}/{media_id}.json"
    xbmc.log(f'[AIOStreams] Requesting subtitles from: {url}', xbmc.LOGINFO)
    return make_request(url, 'Subtitle error')


def download_subtitle_with_language(subtitle_url, language, media_id):
    """
    Download subtitle to local cache with language-coded filename.
    This allows Kodi to properly display subtitle language names.
    """
    import os
    import hashlib

    try:
        # Create subtitles cache directory
        addon_data_path = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
        subtitle_cache_dir = os.path.join(addon_data_path, 'subtitles')

        if not xbmcvfs.exists(subtitle_cache_dir):
            xbmcvfs.mkdirs(subtitle_cache_dir)

        # Create unique filename based on media_id and language
        # Use hash to avoid filesystem issues with special characters
        media_hash = hashlib.md5(media_id.encode()).hexdigest()[:8]

        # Normalize language code (e.g., "English" -> "en", "Spanish" -> "es")
        lang_code = normalize_language_code(language)

        # Determine subtitle extension from URL or default to .srt
        if subtitle_url.endswith('.vtt'):
            ext = '.vtt'
        else:
            ext = '.srt'

        subtitle_filename = f"{media_hash}.{lang_code}{ext}"
        subtitle_path = os.path.join(subtitle_cache_dir, subtitle_filename)

        # Download subtitle content
        timeout = get_timeout()
        response = requests.get(subtitle_url, timeout=timeout)
        response.raise_for_status()

        # Write to file
        with open(subtitle_path, 'wb') as f:
            f.write(response.content)

        xbmc.log(f'[AIOStreams] Downloaded subtitle [{lang_code}] to: {subtitle_path}', xbmc.LOGINFO)
        return subtitle_path

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error downloading subtitle: {e}', xbmc.LOGERROR)
        # Fall back to original URL
        return subtitle_url


def normalize_language_code(language):
    """Convert language name to ISO 639-1 code."""
    # Common language mappings
    lang_map = {
        'english': 'en',
        'spanish': 'es',
        'french': 'fr',
        'german': 'de',
        'italian': 'it',
        'portuguese': 'pt',
        'russian': 'ru',
        'chinese': 'zh',
        'japanese': 'ja',
        'korean': 'ko',
        'arabic': 'ar',
        'hindi': 'hi',
        'dutch': 'nl',
        'polish': 'pl',
        'turkish': 'tr',
        'swedish': 'sv',
        'danish': 'da',
        'norwegian': 'no',
        'finnish': 'fi',
        'czech': 'cs',
        'greek': 'el',
        'hebrew': 'he',
        'thai': 'th',
        'vietnamese': 'vi',
    }

    # Try to get language code
    lang_lower = language.lower().strip()

    # If it's already a 2-letter code, return as-is
    if len(lang_lower) == 2:
        return lang_lower

    # Try to find in mapping
    return lang_map.get(lang_lower, lang_lower[:2])


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
    # Initial check with long TTL to see if we have any cache
    if HAS_MODULES:
        cached = cache.get_cached_meta(content_type, meta_id, ttl_seconds=86400*365)
        if cached:
            # Calculate appropriate TTL based on content
            ttl = get_metadata_ttl(cached)

            # Re-check cache with calculated TTL
            cached = cache.get_cached_meta(content_type, meta_id, ttl_seconds=ttl)
            if cached:
                xbmc.log(f'[AIOStreams] Metadata cache hit for {meta_id} (TTL: {ttl//86400} days)', xbmc.LOGDEBUG)
                return cached

    # Cache miss, fetch from API
    base_url = get_base_url()
    url = f"{base_url}/meta/{content_type}/{meta_id}.json"
    xbmc.log(f'[AIOStreams] Requesting meta from: {url}', xbmc.LOGINFO)
    result = make_request(url, 'Meta error')

    # Store in cache
    if HAS_MODULES and result:
        ttl = get_metadata_ttl(result)
        cache.cache_meta(content_type, meta_id, result)
        xbmc.log(f'[AIOStreams] Cached metadata for {meta_id} (TTL: {ttl//86400} days)', xbmc.LOGDEBUG)

    return result


def create_listitem_with_context(meta, content_type, action_url):
    """Create ListItem with full metadata, artwork, and context menus."""
    title = meta.get('name', 'Unknown')
    list_item = xbmcgui.ListItem(label=title)
    
    # Use InfoTagVideo instead of deprecated setInfo
    info_tag = list_item.getVideoInfoTag()
    info_tag.setTitle(title)
    info_tag.setPlot(meta.get('description', ''))
    
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
    
    # Check if watched in Trakt and add overlay
    if HAS_MODULES and trakt.get_access_token():
        item_id = meta.get('id', '')
        if item_id:
            if content_type == 'movie':
                # For movies, check watched status
                if trakt.is_watched(content_type, item_id):
                    info_tag.setPlaycount(1)
                    list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')
            elif content_type == 'series':
                # For shows, check if fully watched
                progress = trakt.get_show_progress(item_id)
                if progress:
                    aired = progress.get('aired', 0)
                    completed = progress.get('completed', 0)
                    if aired > 0 and aired == completed:
                        # All episodes watched
                        info_tag.setPlaycount(1)
                        list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')
    
    # Set artwork
    if meta.get('poster'):
        list_item.setArt({'poster': meta['poster'], 'thumb': meta['poster']})
    if meta.get('background'):
        list_item.setArt({'fanart': meta['background']})
    if meta.get('logo'):
        list_item.setArt({'clearlogo': meta['logo']})
    
    # Build context menu based on content type
    context_menu = []

    item_id = meta.get('id', '')
    title = meta.get('name', 'Unknown')

    if content_type == 'movie':
        # Movie context menu: Scrape Streams, View Trailer, Mark as Watched, Watchlist
        context_menu.append(('[COLOR lightcoral]Scrape Streams[/COLOR]', f'RunPlugin({get_url(action="show_streams", content_type="movie", media_id=item_id, title=title)})'))

        # Add trailer if available
        trailers = meta.get('trailers', [])
        if trailers and isinstance(trailers, list) and len(trailers) > 0:
            youtube_id = trailers[0].get('ytId', '') or trailers[0].get('source', '')
            if youtube_id:
                trailer_url = f'https://www.youtube.com/watch?v={youtube_id}'
                info_tag.setTrailer(trailer_url)
                play_url = f'plugin://plugin.video.youtube/play/?video_id={youtube_id}'
                context_menu.append(('[COLOR lightcoral]View Trailer[/COLOR]', f'PlayMedia({play_url})'))

        # Trakt context menus if authorized
        if HAS_MODULES and trakt.get_access_token() and item_id:
            is_watched = trakt.is_watched(content_type, item_id)
            if is_watched:
                context_menu.append(('[COLOR lightcoral]Mark Movie As Unwatched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_unwatched", media_type=content_type, imdb_id=item_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Movie As Watched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_watched", media_type=content_type, imdb_id=item_id)})'))

            if trakt.is_in_watchlist(content_type, item_id):
                context_menu.append(('[COLOR lightcoral]Remove from Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_remove_watchlist", media_type=content_type, imdb_id=item_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Add to Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_add_watchlist", media_type=content_type, imdb_id=item_id)})'))

    elif content_type == 'series':
        # Show context menu: View Trailer, Mark as Watched, Watchlist
        # Add trailer if available
        trailers = meta.get('trailerStreams', [])
        if trailers and isinstance(trailers, list) and len(trailers) > 0:
            youtube_id = trailers[0].get('ytId', '') or trailers[0].get('source', '')
            if youtube_id:
                trailer_url = f'https://www.youtube.com/watch?v={youtube_id}'
                info_tag.setTrailer(trailer_url)
                play_url = f'plugin://plugin.video.youtube/play/?video_id={youtube_id}'
                context_menu.append(('[COLOR lightcoral]View Trailer[/COLOR]', f'PlayMedia({play_url})'))

        # Trakt context menus if authorized
        if HAS_MODULES and trakt.get_access_token() and item_id:
            # Check if show is fully watched
            is_watched = False
            progress = trakt.get_show_progress(item_id)
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

            if trakt.is_in_watchlist(content_type, item_id):
                context_menu.append(('[COLOR lightcoral]Remove from Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_remove_watchlist", media_type=content_type, imdb_id=item_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Add to Watchlist[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_add_watchlist", media_type=content_type, imdb_id=item_id)})'))

    list_item.addContextMenuItems(context_menu)

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


def search():
    """Handle search input."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params.get('content_type', 'both')  # Default to both
    query = params.get('query', '').strip()  # Get query and strip whitespace
    skip = int(params.get('skip', 0))

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
        search_unified_internal(query)
        return
    
    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Searching...')
    
    # Perform search
    results = search_catalog(query, content_type, skip=skip)
    progress.close()
    
    if not results or 'metas' not in results:
        xbmcgui.Dialog().notification('AIOStreams', 'No results found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    
    # Apply filters
    if HAS_MODULES and filters:
        results['metas'] = filters.filter_items(results['metas'])
    
    xbmcplugin.setPluginCategory(HANDLE, f'Search: {query}')
    xbmcplugin.setContent(HANDLE, 'movies' if content_type == 'movie' else 'tvshows')
    
    # Display search results
    for meta in results['metas']:
        item_id = meta.get('id')
        item_type = meta.get('type', content_type)

        # Determine if this is a series or movie
        if item_type == 'series':
            # For series, drill down to seasons
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        else:
            # For movies, make them playable directly
            url = get_url(action='play', content_type='movie', imdb_id=item_id)
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)
    
    # Check if next page exists by attempting to fetch it
    next_skip = skip + 20
    next_results = search_catalog(query, content_type, skip=next_skip)
    
    if next_results and 'metas' in next_results and len(next_results['metas']) > 0:
        # Next page has items, show "Load More"
        list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
        url = get_url(action='search', content_type=content_type, query=query, skip=next_skip)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def search_unified_internal(query):
    """Internal unified search with tabbed interface."""
    # Create a selection dialog for tabs
    tabs = ['Movies', 'TV Shows', 'All Results']
    selected = xbmcgui.Dialog().select(f'Search: {query}', tabs)

    if selected == -1:
        # User cancelled
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    if selected == 0:
        # Movies tab
        search_by_tab(query, 'movie')
    elif selected == 1:
        # TV Shows tab
        search_by_tab(query, 'series')
    else:
        # All Results - show both
        search_all_results(query)


def search_by_tab(query, content_type):
    """Search with tab-specific content type for proper poster view."""
    xbmcplugin.setPluginCategory(HANDLE, f'Search {content_type.title()}: {query}')

    # Set proper content type for poster view
    xbmcplugin.setContent(HANDLE, 'movies' if content_type == 'movie' else 'tvshows')

    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', f'Searching {content_type}s...')

    # Perform search
    results = search_catalog(query, content_type, skip=0)
    progress.close()

    if not results or 'metas' not in results or len(results['metas']) == 0:
        xbmcgui.Dialog().notification('AIOStreams', 'No results found', xbmcgui.NOTIFICATION_INFO)
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
            url = get_url(action='play', content_type='movie', imdb_id=item_id)
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    # Load more if available
    next_skip = 20
    next_results = search_catalog(query, content_type, skip=next_skip)
    if next_results and 'metas' in next_results and len(next_results['metas']) > 0:
        list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
        url = get_url(action='search_tab', content_type=content_type, query=query, skip=next_skip)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    xbmcplugin.endOfDirectory(HANDLE)


def add_tab_switcher(query, current_tab):
    """Add tab navigation buttons at the top of search results."""
    tabs = [
        ('Movies', 'movie', '🎬'),
        ('TV Shows', 'series', '📺'),
        ('All', 'both', '🔍')
    ]

    for label, tab_type, icon in tabs:
        if tab_type == current_tab:
            # Current tab - highlighted
            item_label = f'[B][COLOR blue]{icon} {label}[/COLOR][/B]'
        else:
            # Other tabs - clickable
            item_label = f'{icon} {label}'

        list_item = xbmcgui.ListItem(label=item_label)
        list_item.setProperty('IsPlayable', 'false')

        if tab_type != current_tab:
            if tab_type == 'both':
                url = get_url(action='search_unified', query=query)
            else:
                url = get_url(action='search_tab', content_type=tab_type, query=query)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, '', list_item, False)


def search_all_results(query):
    """Show all results (movies and TV shows) in one view."""
    xbmcplugin.setPluginCategory(HANDLE, f'Search: {query}')
    xbmcplugin.setContent(HANDLE, 'videos')

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

        # Add results directly without header
        for meta in movies[:10]:
            item_id = meta.get('id')
            url = get_url(action='play', content_type='movie', imdb_id=item_id)
            list_item = create_listitem_with_context(meta, 'movie', url)
            list_item.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)

        # More link
        if len(movies) > 10:
            list_item = xbmcgui.ListItem(label=f'[COLOR yellow]» View All Movies ({len(movies)} results)[/COLOR]')
            url = get_url(action='search_tab', content_type='movie', query=query)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    # TV Shows Section
    if series_results and 'metas' in series_results and len(series_results['metas']) > 0:
        shows = series_results['metas']
        if HAS_MODULES and filters:
            shows = filters.filter_items(shows)

        # Add results directly without header
        for meta in shows[:10]:
            item_id = meta.get('id')
            url = get_url(action='show_seasons', meta_id=item_id)
            list_item = create_listitem_with_context(meta, 'series', url)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

        # More link
        if len(shows) > 10:
            list_item = xbmcgui.ListItem(label=f'[COLOR yellow]» View All TV Shows ({len(shows)} results)[/COLOR]')
            url = get_url(action='search_tab', content_type='series', query=query)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

    # No results
    if (not movie_results or 'metas' not in movie_results or len(movie_results['metas']) == 0) and \
       (not series_results or 'metas' not in series_results or len(series_results['metas']) == 0):
        xbmcgui.Dialog().notification('AIOStreams', 'No results found', xbmcgui.NOTIFICATION_INFO)

    xbmcplugin.endOfDirectory(HANDLE)


def search_unified():
    """Unified search showing both movies and TV shows."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    query = params.get('query')
    
    if not query:
        keyboard = xbmcgui.Dialog().input('Search', type=xbmcgui.INPUT_ALPHANUM)
        if not keyboard:
            return
        query = keyboard
    
    xbmcplugin.setPluginCategory(HANDLE, f'Search: {query}')
    xbmcplugin.setContent(HANDLE, 'videos')
    
    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Searching movies and TV shows...')
    
    # Search movies
    progress.update(25, 'Searching movies...')
    movie_results = search_catalog(query, 'movie', skip=0)
    
    # Search TV shows
    progress.update(50, 'Searching TV shows...')
    series_results = search_catalog(query, 'series', skip=0)
    
    progress.close()
    
    # Movies Section Header
    if movie_results and 'metas' in movie_results and len(movie_results['metas']) > 0:
        # Apply filters
        movies = movie_results['metas']
        if HAS_MODULES and filters:
            movies = filters.filter_items(movies)
        
        # Add "Movies" category header
        header_item = xbmcgui.ListItem(label='[B][COLOR blue]Movies[/COLOR][/B]')
        header_item.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(HANDLE, '', header_item, False)
        
        # Add movie results (limit to 10)
        for meta in movies[:10]:
            item_id = meta.get('id')
            url = get_url(action='play', content_type='movie', imdb_id=item_id)
            list_item = create_listitem_with_context(meta, 'movie', url)
            list_item.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)
        
        # More movies link
        if len(movies) > 10:
            list_item = xbmcgui.ListItem(label=f'[COLOR yellow]» View All Movies ({len(movies)} results)[/COLOR]')
            url = get_url(action='search', content_type='movie', query=query)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    # TV Shows Section Header
    if series_results and 'metas' in series_results and len(series_results['metas']) > 0:
        # Apply filters
        shows = series_results['metas']
        if HAS_MODULES and filters:
            shows = filters.filter_items(shows)
        
        # Add "TV Shows" category header
        header_item = xbmcgui.ListItem(label='[B][COLOR green]TV Shows[/COLOR][/B]')
        header_item.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(HANDLE, '', header_item, False)
        
        # Add TV show results (limit to 10)
        for meta in shows[:10]:
            item_id = meta.get('id')
            url = get_url(action='show_seasons', meta_id=item_id)
            list_item = create_listitem_with_context(meta, 'series', url)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
        
        # More shows link
        if len(shows) > 10:
            list_item = xbmcgui.ListItem(label=f'[COLOR yellow]» View All TV Shows ({len(shows)} results)[/COLOR]')
            url = get_url(action='search', content_type='series', query=query)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    # No results
    if (not movie_results or 'metas' not in movie_results or len(movie_results['metas']) == 0) and \
       (not series_results or 'metas' not in series_results or len(series_results['metas']) == 0):
        xbmcgui.Dialog().notification('AIOStreams', 'No results found', xbmcgui.NOTIFICATION_INFO)
    
    xbmcplugin.endOfDirectory(HANDLE)




def play():
    """Play content - behavior depends on settings (show streams or auto-play first)."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params['content_type']
    imdb_id = params['imdb_id']

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

    # Fetch streams
    stream_data = get_streams(content_type, media_id)

    if not stream_data or 'streams' not in stream_data or len(stream_data['streams']) == 0:
        xbmcgui.Dialog().notification('AIOStreams', 'No streams available', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    # Check default_behavior setting
    default_behavior = get_setting('default_behavior', 'show_streams')

    # If set to show streams, show dialog instead of auto-playing
    if default_behavior == 'show_streams':
        show_streams_dialog(content_type, media_id, stream_data, title)
        return

    # Otherwise, auto-play first stream
    stream = stream_data['streams'][0]
    stream_url = stream.get('url') or stream.get('externalUrl')

    if not stream_url:
        xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    # Create list item for playback
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')

    # Add subtitles if available
    subtitle_data = get_subtitles(content_type, media_id)
    if subtitle_data and 'subtitles' in subtitle_data:
        subtitle_paths = []
        for subtitle in subtitle_data['subtitles']:
            sub_url = subtitle.get('url')
            if sub_url:
                # Download subtitle with language-coded filename for proper Kodi display
                lang = subtitle.get('lang', 'unknown')
                sub_path = download_subtitle_with_language(sub_url, lang, media_id)
                subtitle_paths.append(sub_path)
                xbmc.log(f'[AIOStreams] Added subtitle [{lang}]: {sub_path}', xbmc.LOGINFO)

        if subtitle_paths:
            list_item.setSubtitles(subtitle_paths)

    # Set media info for scrobbling
    if HAS_MODULES and PLAYER:
        scrobble_type = 'movie' if content_type == 'movie' else 'episode'
        PLAYER.set_media_info(scrobble_type, imdb_id, season, episode)

    # Set resolved URL for playback
    xbmcplugin.setResolvedUrl(HANDLE, True, list_item)


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


def create_stream_list_items(streams, strip_emojis_flag=False):
    """
    Create formatted labels for stream selection dialog with full multi-line display.
    Shows all 5+ lines: name, codec, audio, size, language, filename.

    Args:
        streams: List of stream dictionaries
        strip_emojis_flag: If True, remove emojis. Default False (keep emojis - textbox can render them)

    Returns:
        List of formatted label strings for custom dialog
    """
    import re

    def strip_emojis(text):
        """Remove emoji characters that don't render properly in Kodi."""
        # Remove emoji ranges and other problematic Unicode characters
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text)

    labels = []

    for stream in streams:
        stream_name = stream.get('name', stream.get('title', 'Unknown Stream'))
        description = stream.get('description', '')

        # Optionally strip emojis (custom textbox controls can usually render them)
        if strip_emojis_flag:
            stream_name = strip_emojis(stream_name).strip()
            description = strip_emojis(description).strip() if description else ''
        else:
            stream_name = stream_name.strip()
            description = description.strip() if description else ''

        # Build multi-line label with all lines from description
        # Line 0: Stream name (service, source, quality)
        # Line 1: Codec info (BluRay, HEVC, etc.)
        # Line 2: Audio info (DTS, Atmos, etc.)
        # Line 3: Size info (GB/MB)
        # Line 4: Language info (Multi, French, etc.)
        # Line 5: Filename (optional)

        lines = [stream_name]

        if description:
            # Split description by newlines
            desc_lines = [line.strip() for line in description.split('\n') if line.strip()]
            # Add all description lines (typically 4-5 lines)
            lines.extend(desc_lines)

        # Join all lines with newline
        label = '\n'.join(lines)
        labels.append(label)

    return labels


def select_stream():
    """TMDBHelper select stream - show dialog to select from available streams."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params['content_type']
    imdb_id = params['imdb_id']
    title = params.get('title', '')
    
    # Format media ID for AIOStreams API
    if content_type == 'movie':
        media_id = imdb_id
        season = None
        episode = None
    else:
        season = params.get('season')
        episode = params.get('episode')
        media_id = f"{imdb_id}:{season}:{episode}"
    
    # Fetch streams
    stream_data = get_streams(content_type, media_id)
    
    if not stream_data or 'streams' not in stream_data or len(stream_data['streams']) == 0:
        xbmcgui.Dialog().notification('AIOStreams', 'No streams available', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    
    # Prepare metadata for custom source select dialog
    metadata = {
        'title': title or 'Select Stream',
        'fanart': '',  # Could be populated from API if available
        'clearlogo': ''  # Could be populated from API if available
    }

    # Use Kodi's built-in select dialog with ListItems
    xbmc.log(f'[AIOStreams] Showing stream selection dialog with {len(stream_data["streams"])} streams', xbmc.LOGDEBUG)

    # Create formatted labels for custom dialog (strip emojis - they render as boxes)
    stream_labels = create_stream_list_items(stream_data['streams'], strip_emojis_flag=True)

    # Show custom multi-line dialog
    dialog = StreamSelectDialog(
        "script-stream-select.xml",
        ADDON_PATH,
        "default",
        "1080i",
        streams=stream_labels,
        title=f"Select Stream ({len(stream_labels)} available)"
    )
    dialog.doModal()
    selected = dialog.selected_index
    del dialog

    if selected is None or selected < 0:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    
    # Get selected stream
    stream = stream_data['streams'][selected]
    stream_url = stream.get('url') or stream.get('externalUrl')
    
    if not stream_url:
        xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    
    # Create list item for playback
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')
    
    # Add subtitles if available
    subtitle_data = get_subtitles(content_type, media_id)
    if subtitle_data and 'subtitles' in subtitle_data:
        subtitle_paths = []
        for subtitle in subtitle_data['subtitles']:
            sub_url = subtitle.get('url')
            if sub_url:
                # Download subtitle with language-coded filename for proper Kodi display
                lang = subtitle.get('lang', 'unknown')
                sub_path = download_subtitle_with_language(sub_url, lang, media_id)
                subtitle_paths.append(sub_path)
                xbmc.log(f'[AIOStreams] Added subtitle [{lang}]: {sub_path}', xbmc.LOGINFO)

        if subtitle_paths:
            list_item.setSubtitles(subtitle_paths)
    
    # Set media info for scrobbling
    if HAS_MODULES and PLAYER:
        scrobble_type = 'movie' if content_type == 'movie' else 'episode'
        PLAYER.set_media_info(scrobble_type, imdb_id, season, episode)
    
    # Set resolved URL for playback
    xbmcplugin.setResolvedUrl(HANDLE, True, list_item)


def movie_lists():
    """Movie lists submenu."""
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
        
        if genre_extra and genre_extra.get('options'):
            url = get_url(action='catalog_genres', catalog_id=catalog_id, content_type=content_type, catalog_name=catalog_name)
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
    params = dict(parse_qsl(sys.argv[2][1:]))
    catalog_id = params['catalog_id']
    content_type = params['content_type']
    catalog_name = params.get('catalog_name', 'Catalog')
    genre = params.get('genre')
    skip = int(params.get('skip', 0))

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
            url = get_url(action='play', content_type='movie', imdb_id=item_id)
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
        # Show "Load More" if we got a full page
        list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
        url = get_url(action='browse_catalog', catalog_id=catalog_id, content_type=content_type,
                      genre=genre if genre else '', skip=next_skip)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def show_streams():
    """Show streams for a catalog item in a dialog window."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params['content_type']
    media_id = params['media_id']
    title = params.get('title', 'Unknown')

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

    # Always show streams dialog (ignore default behavior - user explicitly requested stream selection)
    show_streams_dialog(content_type, media_id, stream_data, title)


def show_streams_dialog(content_type, media_id, stream_data, title):
    """Show streams in a selection dialog."""
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
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # Prepare metadata for custom source select dialog
    metadata = {
        'title': title,
        'fanart': '',  # Could be populated from API if available
        'clearlogo': ''  # Could be populated from API if available
    }

    # Use Kodi's built-in select dialog with ListItems
    xbmc.log(f'[AIOStreams] Showing stream selection dialog with {len(stream_data["streams"])} streams', xbmc.LOGDEBUG)

    # Create formatted labels for custom dialog (strip emojis - they render as boxes)
    stream_labels = create_stream_list_items(stream_data['streams'], strip_emojis_flag=True)

    # Show custom multi-line dialog
    dialog = StreamSelectDialog(
        "script-stream-select.xml",
        ADDON_PATH,
        "default",
        "1080i",
        streams=stream_labels,
        title=f"Select Stream ({len(stream_labels)} available)"
    )
    dialog.doModal()
    selected = dialog.selected_index
    del dialog

    if selected is None or selected < 0:
        # User cancelled
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    # Record selection for learning
    if HAS_MODULES:
        stream_mgr.record_stream_selection(stream_data['streams'][selected].get('name', ''))

    # Play selected stream
    play_stream_by_index(content_type, media_id, stream_data, selected)


def play_stream_by_index(content_type, media_id, stream_data, index):
    """Play a stream by its index in the stream list."""
    if index >= len(stream_data['streams']):
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid stream index', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return False

    stream = stream_data['streams'][index]
    stream_url = stream.get('url') or stream.get('externalUrl')

    if not stream_url:
        xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
        return False

    # Create list item for playback
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')

    # Add subtitles if available
    subtitle_data = get_subtitles(content_type, media_id)
    if subtitle_data and 'subtitles' in subtitle_data:
        subtitle_urls = []
        for subtitle in subtitle_data['subtitles']:
            sub_url = subtitle.get('url')
            if sub_url:
                subtitle_urls.append(sub_url)
                xbmc.log(f'[AIOStreams] Added subtitle: {subtitle.get("lang", "unknown")} - {sub_url}', xbmc.LOGINFO)

        if subtitle_urls:
            list_item.setSubtitles(subtitle_urls)

    # Set media info for scrobbling
    if HAS_MODULES and PLAYER:
        # Parse media_id for episodes (format: imdb_id:season:episode)
        if content_type == 'series' and ':' in media_id:
            parts = media_id.split(':')
            imdb_id = parts[0]
            season = parts[1] if len(parts) > 1 else None
            episode = parts[2] if len(parts) > 2 else None
            PLAYER.set_media_info('episode', imdb_id, season, episode)
        else:
            PLAYER.set_media_info('movie', media_id, None, None)

    # Set resolved URL for playback
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

    return True


def try_next_streams(content_type, media_id, stream_data, start_index=1):
    """Try to play streams sequentially starting from start_index."""
    for i in range(start_index, len(stream_data['streams'])):
        success = play_stream_by_index(content_type, media_id, stream_data, i)
        if success:
            return

    # All streams failed
    xbmcgui.Dialog().notification('AIOStreams', 'All streams failed', xbmcgui.NOTIFICATION_ERROR)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def show_seasons():
    """Show seasons for a TV series."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    meta_id = params['meta_id']
    
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

        # Set playcount if watched
        if is_season_watched:
            info_tag.setPlaycount(1)
            list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')

        if meta.get('poster'):
            list_item.setArt({'poster': meta['poster'], 'thumb': meta['poster']})
        if meta.get('background'):
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


def show_episodes():
    """Show episodes for a specific season."""
    params = dict(parse_qsl(sys.argv[2][1:]))
    meta_id = params['meta_id']
    season = int(params['season'])
    
    meta_data = get_meta('series', meta_id)
    
    if not meta_data or 'meta' not in meta_data:
        xbmcgui.Dialog().notification('AIOStreams', 'Series info not found', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    meta = meta_data['meta']
    series_name = meta.get('name', 'Unknown Series')
    
    xbmcplugin.setPluginCategory(HANDLE, f'{series_name} - Season {season}')
    xbmcplugin.setContent(HANDLE, 'episodes')
    
    videos = meta.get('videos', [])
    episodes = [v for v in videos if v.get('season') == season]
    
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

        # Set playcount if watched
        if is_watched:
            info_tag.setPlaycount(1)
            list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')

        # Add episode context menu
        episode_title = f'{series_name} - S{season:02d}E{episode_num:02d}'
        episode_media_id = f"{meta_id}:{season}:{episode_num}"
        context_menu = [
            ('[COLOR lightcoral]Scrape Streams[/COLOR]', f'RunPlugin({get_url(action="show_streams", content_type="series", media_id=episode_media_id, title=episode_title)})'),
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
        url = get_url(action='play', content_type='series', imdb_id=meta_id, season=season, episode=episode_num)
        list_item.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)
    
    xbmcplugin.endOfDirectory(HANDLE)


# Trakt functions
def trakt_menu():
    """Trakt catalogs submenu."""
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return
    
    xbmcplugin.setPluginCategory(HANDLE, 'Trakt Catalogs')
    xbmcplugin.setContent(HANDLE, 'videos')
    
    menu_items = [
        {'label': 'Next Up', 'url': get_url(action='trakt_next_up'), 'icon': 'DefaultTVShows.png'},
        {'label': 'Watchlist - Movies', 'url': get_url(action='trakt_watchlist', media_type='movies'), 'icon': 'DefaultMovies.png'},
        {'label': 'Watchlist - Shows', 'url': get_url(action='trakt_watchlist', media_type='shows'), 'icon': 'DefaultTVShows.png'},
        {'label': 'Collection - Movies', 'url': get_url(action='trakt_collection', media_type='movies'), 'icon': 'DefaultMovies.png'},
        {'label': 'Collection - Shows', 'url': get_url(action='trakt_collection', media_type='shows'), 'icon': 'DefaultTVShows.png'}
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


def trakt_watchlist():
    """Display Trakt watchlist with auto-sync."""
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movies')

    # Auto-sync if enabled (throttled to 5 minutes)
    auto_sync_enabled = get_setting('trakt_sync_auto', 'true') == 'true'
    if auto_sync_enabled:
        try:
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
            db = TraktSyncDatabase()
            db.sync_activities(silent=True)  # Silent auto-sync
        except Exception as e:
            xbmc.log(f'[AIOStreams] Auto-sync failed: {e}', xbmc.LOGWARNING)
    
    # Fetch from database (instant) - use activities sync database
    try:
        from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
        db = TraktSyncDatabase()
        
        # Query watchlist from database
        mediatype_filter = 'movie' if media_type == 'movies' else 'show'
        items_raw = db.fetchall(
            "SELECT * FROM watchlist WHERE mediatype=? ORDER BY listed_at DESC",
            (mediatype_filter,)
        )
        
        if not items_raw:
            # Fallback to old Trakt API method if database is empty
            xbmc.log('[AIOStreams] Watchlist database empty, using Trakt API fallback', xbmc.LOGDEBUG)
            items = trakt.get_watchlist(media_type)
        else:
            # Convert database format to Trakt API format for compatibility
            items = []
            for row in items_raw:
                item_wrapper = {
                    'listed_at': row.get('listed_at'),
                    media_type[:-1] if media_type.endswith('s') else media_type: {
                        'ids': {
                            'trakt': row.get('trakt_id'),
                            'imdb': row.get('imdb_id')
                        }
                    }
                }
                items.append(item_wrapper)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error accessing watchlist database: {e}', xbmc.LOGWARNING)
        # Fallback to old method
        items = trakt.get_watchlist(media_type)

    if not items:
        xbmcgui.Dialog().notification('AIOStreams', 'Watchlist is empty', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Trakt Watchlist - {media_type.capitalize()}')
    xbmcplugin.setContent(HANDLE, 'movies' if media_type == 'movies' else 'tvshows')

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

        # Try to get artwork from cached AIOStreams metadata (fast cache lookup)
        if HAS_MODULES:
            cached_meta = cache.get_cached_meta(content_type, item_id)
            if cached_meta and 'meta' in cached_meta:
                cached_data = cached_meta['meta']
                # Enhance with cached artwork and other metadata
                meta['poster'] = cached_data.get('poster', '')
                meta['background'] = cached_data.get('background', '')
                meta['logo'] = cached_data.get('logo', '')
                # Get cast from cached AIOStreams data (includes photos)
                meta['app_extras'] = cached_data.get('app_extras', {})
                # Keep Trakt data for text fields, only use AIOStreams for what's better
                if not meta['description']:
                    meta['description'] = cached_data.get('description', '')
            elif item_id:
                # Fetch metadata if not cached (needed for widgets)
                meta_data = get_meta(content_type, item_id)
                if meta_data and 'meta' in meta_data:
                    cached_data = meta_data['meta']
                    meta['poster'] = cached_data.get('poster', '')
                    meta['background'] = cached_data.get('background', '')
                    meta['logo'] = cached_data.get('logo', '')
                    meta['app_extras'] = cached_data.get('app_extras', {})
                    if not meta['description']:
                        meta['description'] = cached_data.get('description', '')

        if content_type == 'series':
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        else:
            url = get_url(action='play', content_type='movie', imdb_id=item_id)
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def trakt_collection():
    """Display Trakt collection with auto-sync."""
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movies')

    # Auto-sync if enabled (throttled to 5 minutes)
    auto_sync_enabled = get_setting('trakt_sync_auto', 'true') == 'true'
    if auto_sync_enabled:
        try:
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
            db = TraktSyncDatabase()
            db.sync_activities(silent=True)  # Silent auto-sync
        except Exception as e:
            xbmc.log(f'[AIOStreams] Auto-sync failed: {e}', xbmc.LOGWARNING)
    
    # Fetch from database (instant) - use activities sync database
    try:
        from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
        db = TraktSyncDatabase()
        
        # Query collection from database based on media type
        if media_type == 'movies':
            items_raw = db.fetchall(
                "SELECT * FROM movies WHERE collected=1 ORDER BY collected_at DESC"
            )
        else:  # shows
            # Get all shows that have collected episodes
            items_raw = db.fetchall(
                "SELECT DISTINCT s.* FROM shows s JOIN episodes e ON s.trakt_id = e.trakt_show_id WHERE e.collected=1"
            )
        
        if not items_raw:
            # Fallback to old Trakt API method if database is empty
            xbmc.log('[AIOStreams] Collection database empty, using Trakt API fallback', xbmc.LOGDEBUG)
            items = trakt.get_collection(media_type)
        else:
            # Convert database format to Trakt API format for compatibility
            items = []
            for row in items_raw:
                item_wrapper = {
                    'collected_at': row.get('collected_at') if media_type == 'movies' else row.get('last_updated'),
                    media_type[:-1] if media_type.endswith('s') else media_type: {
                        'ids': {
                            'trakt': row.get('trakt_id'),
                            'imdb': row.get('imdb_id')
                        }
                    }
                }
                items.append(item_wrapper)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error accessing collection database: {e}', xbmc.LOGWARNING)
        # Fallback to old method
        items = trakt.get_collection(media_type)

    if not items:
        xbmcgui.Dialog().notification('AIOStreams', 'Collection is empty', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Trakt Collection - {media_type.capitalize()}')
    xbmcplugin.setContent(HANDLE, 'movies' if media_type == 'movies' else 'tvshows')

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

        # Try to get artwork and cast from cached AIOStreams metadata (fast cache lookup)
        if HAS_MODULES:
            cached_meta = cache.get_cached_meta(content_type, item_id)
            if cached_meta and 'meta' in cached_meta:
                cached_data = cached_meta['meta']
                meta['poster'] = cached_data.get('poster', '')
                meta['background'] = cached_data.get('background', '')
                meta['logo'] = cached_data.get('logo', '')
                # Get cast from cached AIOStreams data (includes photos)
                meta['app_extras'] = cached_data.get('app_extras', {})
                if not meta['description']:
                    meta['description'] = cached_data.get('description', '')
            elif item_id:
                # Fetch metadata if not cached (needed for widgets)
                meta_data = get_meta(content_type, item_id)
                if meta_data and 'meta' in meta_data:
                    cached_data = meta_data['meta']
                    meta['poster'] = cached_data.get('poster', '')
                    meta['background'] = cached_data.get('background', '')
                    meta['logo'] = cached_data.get('logo', '')
                    meta['app_extras'] = cached_data.get('app_extras', {})
                    if not meta['description']:
                        meta['description'] = cached_data.get('description', '')
        
        if content_type == 'series':
            url = get_url(action='show_seasons', meta_id=item_id)
            is_folder = True
        else:
            url = get_url(action='play', content_type='movie', imdb_id=item_id)
            is_folder = False

        list_item = create_listitem_with_context(meta, content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(HANDLE)



def trakt_next_up():
    """Display next episodes to watch using pure SQL - ZERO API calls!

    Uses Seren's approach: calculates next episode from local database.
    All episodes are stored during sync, so we can find the next unwatched
    episode purely from SQL without calling the API.
    """
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Next Up')
    xbmcplugin.setContent(HANDLE, 'episodes')

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
        xbmcgui.Dialog().notification('AIOStreams', 'No shows in progress', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmc.log(f'[AIOStreams] Next Up: Found {len(next_episodes)} shows with next episodes', xbmc.LOGINFO)

    # Process each episode
    for ep_data in next_episodes:
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

        if show_imdb:
            # First try cache, then fetch from API if needed
            meta_result = None
            if HAS_MODULES:
                cached_meta = cache.get_cached_meta('series', show_imdb)
                if cached_meta and 'meta' in cached_meta:
                    meta_result = cached_meta
                    xbmc.log(f'[AIOStreams] Next Up: Using cached metadata for {show_title}', xbmc.LOGDEBUG)

            # If not cached, fetch from API
            if not meta_result:
                meta_result = get_meta('series', show_imdb)
                xbmc.log(f'[AIOStreams] Next Up: Fetched metadata from API for {show_title}', xbmc.LOGDEBUG)

            # Extract metadata
            if meta_result and 'meta' in meta_result:
                meta_data = meta_result['meta']
                # Get show title from metadata if available
                show_title = meta_data.get('name', show_title)
                poster = meta_data.get('poster', '')
                fanart = meta_data.get('background', '')
                logo = meta_data.get('logo', '')

                # Get episode-specific data
                videos = meta_data.get('videos', [])
                for video in videos:
                    if video.get('season') == season and video.get('episode') == episode:
                        episode_thumb = video.get('thumbnail', '')
                        episode_title = video.get('title', episode_title)
                        episode_overview = video.get('description', '')
                        break

        label = f'{show_title} S{season:02d}E{episode:02d}'

        list_item = xbmcgui.ListItem(label=label)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(episode_title)
        info_tag.setTvShowTitle(show_title)
        info_tag.setSeason(season)
        info_tag.setEpisode(episode)
        info_tag.setMediaType('episode')
        info_tag.setPlot(episode_overview)

        # Set artwork
        if episode_thumb:
            list_item.setArt({'thumb': episode_thumb})
            if poster:
                list_item.setArt({'poster': poster})
        elif poster:
            list_item.setArt({'thumb': poster, 'poster': poster})

        if fanart:
            list_item.setArt({'fanart': fanart})

        if logo:
            list_item.setArt({'clearlogo': logo})

        # Build context menu
        episode_media_id = f"{show_imdb}:{season}:{episode}"
        episode_title_str = f'{show_title} - S{season:02d}E{episode:02d}'
        context_menu = [
            ('[COLOR lightcoral]Scrape Streams[/COLOR]', f'RunPlugin({get_url(action="show_streams", content_type="series", media_id=episode_media_id, title=episode_title_str)})'),
            ('[COLOR lightcoral]Browse Show[/COLOR]', f'ActivateWindow(Videos,{sys.argv[0]}?{urlencode({"action": "show_seasons", "meta_id": show_imdb})},return)')
        ]

        # Add Trakt context menu items if authorized
        if HAS_MODULES and trakt.get_access_token() and show_imdb:
            # Check if this specific episode is watched from database
            is_episode_watched = trakt.is_episode_watched(show_imdb, season, episode)

            if is_episode_watched:
                context_menu.append(('[COLOR lightcoral]Mark Episode As Unwatched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_unwatched", media_type="show", imdb_id=show_imdb, season=season, episode=episode)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Episode As Watched[/COLOR]',
                                    f'RunPlugin({get_url(action="trakt_mark_watched", media_type="show", imdb_id=show_imdb, season=season, episode=episode)})'))

            # Stop Watching (Drop) option
            context_menu.append(('[COLOR lightcoral]Stop Watching (Drop) Trakt[/COLOR]',
                                f'RunPlugin({get_url(action="trakt_hide_from_progress", media_type="series", imdb_id=show_imdb)})'))

            # Unhide/Undrop option
            context_menu.append(('[COLOR lightgreen]Resume Watching (Unhide) Trakt[/COLOR]',
                                f'RunPlugin({get_url(action="trakt_unhide_from_progress", media_type="series", imdb_id=show_imdb)})'))

        if context_menu:
            list_item.addContextMenuItems(context_menu)

        # Make episodes directly playable
        if show_imdb:
            url = get_url(action='play', content_type='series', imdb_id=show_imdb, season=season, episode=episode)
            list_item.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)

    xbmcplugin.endOfDirectory(HANDLE)


def show_related():
    """Show related/similar content."""
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

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

    # Display related items
    for item in items:
        item_type = 'movie' if 'movie' in item else 'show'
        item_data = item.get('movie') or item.get('show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')

        if not item_id:
            continue

        # Use the correct content type for this specific item
        item_content_type = 'movie' if item_type == 'movie' else 'series'

        # Fetch full metadata
        meta_data = get_meta(item_content_type, item_id)

        if meta_data and 'meta' in meta_data:
            meta = meta_data['meta']
        else:
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
            url = get_url(action='play', content_type='movie', imdb_id=item_id, title=meta.get('name', 'Unknown'))
            is_folder = False

        list_item = create_listitem_with_context(meta, item_content_type, url)

        # Set IsPlayable property for movies
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def trakt_hide_show():
    """Hide a show from progress."""
    if not HAS_MODULES:
        return
    
    params = dict(parse_qsl(sys.argv[2][1:]))
    show_trakt_id = params.get('show_trakt_id', '')
    
    if show_trakt_id:
        trakt.hide_show_from_progress(int(show_trakt_id))
        xbmc.executebuiltin('Container.Refresh')


def trakt_auth():
    """Authorize with Trakt."""
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return
    
    trakt.authorize()


def trakt_revoke():
    """Revoke Trakt authorization."""
    if not HAS_MODULES:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return
    
    trakt.revoke_authorization()


def trakt_add_watchlist():
    """Add item to Trakt watchlist."""
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        trakt.add_to_watchlist(media_type, imdb_id)
        xbmc.executebuiltin('Container.Refresh')
        # Trigger widget refresh in background
        try:
            from resources.lib import utils
            utils.trigger_background_refresh(delay=0.5)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


def trakt_remove_watchlist():
    """Remove item from Trakt watchlist."""
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    season = params.get('season')
    episode = params.get('episode')

    if imdb_id:
        season_int = int(season) if season else None
        episode_int = int(episode) if episode else None
        trakt.remove_from_watchlist(media_type, imdb_id, season_int, episode_int)
        xbmc.executebuiltin('Container.Refresh')
        # Trigger widget refresh in background
        try:
            from resources.lib import utils
            utils.trigger_background_refresh(delay=0.5)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


def trakt_mark_watched():
    """Mark item as watched on Trakt."""
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    season = params.get('season')
    episode = params.get('episode')
    playback_id = params.get('playback_id', '')

    if imdb_id:
        season_int = int(season) if season else None
        episode_int = int(episode) if episode else None
        playback_id_int = int(playback_id) if playback_id else None
        trakt.mark_watched(media_type, imdb_id, season_int, episode_int, playback_id_int)
        xbmc.executebuiltin('Container.Refresh')
        # Trigger widget refresh in background
        try:
            from resources.lib import utils
            utils.trigger_background_refresh(delay=0.5)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


def trakt_mark_unwatched():
    """Mark item as unwatched on Trakt."""
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    season = params.get('season')
    episode = params.get('episode')

    if imdb_id:
        season_int = int(season) if season else None
        episode_int = int(episode) if episode else None
        trakt.mark_unwatched(media_type, imdb_id, season_int, episode_int)
        xbmc.executebuiltin('Container.Refresh')
        # Trigger widget refresh in background
        try:
            from resources.lib import utils
            utils.trigger_background_refresh(delay=0.5)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


def trakt_remove_playback():
    """Remove item from continue watching without marking as watched."""
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    playback_id = params.get('playback_id', '')

    if playback_id:
        trakt.remove_from_playback(int(playback_id))


def trakt_hide_from_progress():
    """Hide item from Trakt progress (Stop Watching/Drop)."""
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        success = trakt.hide_from_progress(media_type, imdb_id)
        if success:
            # Refresh current container immediately
            xbmc.executebuiltin('Container.Refresh')
            # Trigger widget refresh in background
            try:
                from resources.lib import utils
                utils.trigger_background_refresh(delay=0.5)
            except Exception as e:
                xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


def trakt_unhide_from_progress():
    """Unhide item from Trakt progress (Undrop/Resume Watching)."""
    if not HAS_MODULES:
        return

    params = dict(parse_qsl(sys.argv[2][1:]))
    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        success = trakt.unhide_from_progress(media_type, imdb_id)
        if success:
            # Refresh current container immediately
            xbmc.executebuiltin('Container.Refresh')
            # Trigger widget refresh in background
            try:
                from resources.lib import utils
                utils.trigger_background_refresh(delay=0.5)
            except Exception as e:
                xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


# Maintenance Tools

def clear_cache():
    """Clear all cached data including Trakt progress cache and manifest."""
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
            db.commit()
            
            xbmc.log('[AIOStreams] Trakt database cleared successfully', xbmc.LOGINFO)
            xbmcgui.Dialog().notification('AIOStreams', 'Trakt database cleared', xbmcgui.NOTIFICATION_INFO)
        finally:
            db.disconnect()
            
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to clear Trakt database: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear database', xbmcgui.NOTIFICATION_ERROR)


def rebuild_trakt_database():
    """Rebuild Trakt database by clearing and forcing a fresh sync."""
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
    """Show information about the Trakt database."""
    if not HAS_MODULES:
        return
    
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        
        db = TraktSyncDatabase()
        if not db.connect():
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return
        
        try:
            # Get counts from each table
            show_count = db.execute('SELECT COUNT(*) as count FROM shows').fetchone()['count']
            episode_count = db.execute('SELECT COUNT(*) as count FROM episodes').fetchone()['count']
            movie_count = db.execute('SELECT COUNT(*) as count FROM movies').fetchone()['count']
            watchlist_count = db.execute('SELECT COUNT(*) as count FROM watchlist').fetchone()['count']
            
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
                f'Shows: {show_count}\n'
                f'Episodes: {episode_count}\n'
                f'Movies: {movie_count}\n'
                f'Watchlist: {watchlist_count}\n\n'
                f'Last Sync: {last_sync_str}\n'
                f'Database Size: {db_size:.1f} KB'
            )
            
            xbmcgui.Dialog().ok('Trakt Database Info', info_text)
            
        finally:
            db.disconnect()
            
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to get database info: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to get database info', xbmcgui.NOTIFICATION_ERROR)


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
    params = dict(parse_qsl(sys.argv[2][1:]))
    content_type = params.get('content_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    title = params.get('title', 'Unknown')

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
            xbmc.executebuiltin(f'RunPlugin({get_url(action="show_streams", content_type="movie", media_id=imdb_id, title=title)})')
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


def router(params):
    """Route to the appropriate function based on parameters."""
    action = params.get('action', '')
    
    if action == 'search':
        search()
    elif action == 'search_unified':
        search_unified()
    elif action == 'search_tab':
        # Tab-specific search with proper content type
        query = params.get('query', '')
        content_type = params.get('content_type', 'movie')
        skip = int(params.get('skip', 0))

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
                        url = get_url(action='play', content_type='movie', imdb_id=item_id)
                        is_folder = False
                    list_item = create_listitem_with_context(meta, content_type, url)

                    # Set IsPlayable property for movies
                    if not is_folder:
                        list_item.setProperty('IsPlayable', 'true')

                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

                # Check for next page
                next_skip = skip + 20
                next_results = search_catalog(query, content_type, skip=next_skip)
                if next_results and 'metas' in next_results and len(next_results['metas']) > 0:
                    list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
                    url = get_url(action='search_tab', content_type=content_type, query=query, skip=next_skip)
                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

            xbmcplugin.endOfDirectory(HANDLE)
        else:
            # Initial search - show with tabs
            search_by_tab(query, content_type)
    elif action == 'play':
        play()
    elif action == 'select_stream':
        select_stream()
    elif action == 'movie_lists':
        movie_lists()
    elif action == 'series_lists':
        series_lists()
    elif action == 'catalogs':
        list_catalogs()
    elif action == 'catalog_genres':
        list_catalog_genres()
    elif action == 'browse_catalog':
        browse_catalog()
    elif action == 'show_streams':
        show_streams()
    elif action == 'show_seasons':
        show_seasons()
    elif action == 'show_episodes':
        show_episodes()
    elif action == 'trakt_menu':
        trakt_menu()
    elif action == 'force_trakt_sync':
        force_trakt_sync()
    elif action == 'trakt_watchlist':
        trakt_watchlist()
    elif action == 'trakt_collection':
        trakt_collection()
    elif action == 'trakt_next_up':
        trakt_next_up()
    elif action == 'show_related':
        show_related()
    elif action == 'trakt_hide_show':
        trakt_hide_show()
    elif action == 'trakt_auth':
        trakt_auth()
    elif action == 'trakt_revoke':
        trakt_revoke()
    elif action == 'trakt_add_watchlist':
        trakt_add_watchlist()
    elif action == 'trakt_remove_watchlist':
        trakt_remove_watchlist()
    elif action == 'trakt_mark_watched':
        trakt_mark_watched()
    elif action == 'trakt_mark_unwatched':
        trakt_mark_unwatched()
    elif action == 'trakt_remove_playback':
        trakt_remove_playback()
    elif action == 'trakt_hide_from_progress':
        trakt_hide_from_progress()
    elif action == 'trakt_unhide_from_progress':
        trakt_unhide_from_progress()
    elif action == 'clear_cache':
        clear_cache()
    elif action == 'clear_stream_stats':
        clear_stream_stats()
    elif action == 'clear_preferences':
        clear_preferences()
    elif action == 'clear_trakt_database':
        clear_trakt_database()
    elif action == 'rebuild_trakt_database':
        rebuild_trakt_database()
    elif action == 'show_database_info':
        show_database_info()
    elif action == 'vacuum_database':
        vacuum_database()
    elif action == 'test_connection':
        test_connection()
    elif action == 'quick_actions':
        quick_actions()
    elif params:
        index()
    else:
        index()


if __name__ == '__main__':
    params = dict(parse_qsl(sys.argv[2][1:]))
    router(params)
