"""Shared Kodi media presentation and navigation parameter helpers."""
from urllib.parse import urlencode

from .media import MediaRef


def plugin_url(action, **params):
    """Build a callback URL for the add-on, independent of the current script."""
    route = {'action': action}
    route.update(params)
    return 'plugin://plugin.video.aiostreams/?{}'.format(urlencode(route))


def media_action_params(action, media, **extra):
    """Return explicit route parameters for a normalized media reference."""
    media = media if isinstance(media, MediaRef) else MediaRef.from_meta(media)
    params = dict(extra)
    if action in ('show_seasons', 'show_episodes', 'browse_show'):
        params.setdefault('meta_id', media.navigation_id)
    elif action in ('play', 'play_first', 'select_stream', 'show_streams'):
        params.setdefault('content_type', media.content_type)
        params.setdefault('imdb_id', media.playback_id)
    params.setdefault('title', media.title)
    if media.poster:
        params.setdefault('poster', media.poster)
    if media.fanart:
        params.setdefault('fanart', media.fanart)
    return params


def apply_media_identity(list_item, media):
    """Expose a normalized media reference through standard Kodi item properties."""
    media = media if isinstance(media, MediaRef) else MediaRef.from_meta(media)
    list_item.setProperty('id', media.navigation_id)
    list_item.setProperty('meta_id', media.navigation_id)
    list_item.setProperty('imdb_id', media.imdb_id or '')
    list_item.setProperty('tmdb_id', media.tmdb_id or '')
    list_item.setProperty('playable_id', media.playable_id or '')
    list_item.setProperty('content_type', media.content_type)
    return list_item


def create_media_list_item(meta, media):
    """Create the common ListItem shell and expose normalized identity to skins."""
    import xbmcgui

    media = media if isinstance(media, MediaRef) else MediaRef.from_meta(meta)
    list_item = xbmcgui.ListItem(label=media.title)
    info_tag = list_item.getVideoInfoTag()
    info_tag.setTitle(media.title)
    info_tag.setPlot(meta.get('description', ''))
    apply_media_identity(list_item, media)
    return list_item, info_tag


class PresentationDependencies:
    """Add-on collaborators used while enriching a Kodi media item."""

    def __init__(self, has_modules, get_url, format_date, get_cached_clearlogo_path, ensure_clearlogo_cached, redact_identifier):
        self.has_modules = has_modules
        self.get_url = get_url
        self.format_date = format_date
        self.get_cached_clearlogo_path = get_cached_clearlogo_path
        self.ensure_clearlogo_cached = ensure_clearlogo_cached
        self.redact_identifier = redact_identifier


def create_listitem_with_context(meta, content_type, action_url, dependencies):
    """Create ListItem with full metadata, artwork, and context menus."""
    import xbmc
    from resources.lib import trakt
    media = MediaRef.from_meta(meta, content_type)
    content_type = media.content_type
    list_item, info_tag = create_media_list_item(meta, media)
    title = media.title

    # Set genres (handle both list and comma-separated string)
    genres_data = meta.get('genres', [])
    genres_list = []
    if isinstance(genres_data, str):
        genres_list = [g.strip() for g in genres_data.split(',') if g.strip()]
    elif isinstance(genres_data, list):
        for g in genres_data:
            if isinstance(g, str):
                genres_list.append(g)
            elif isinstance(g, dict):
                # Handle dicts by extracting name if present
                name = g.get('name') or g.get('label')
                if name: genres_list.append(str(name))
            else:
                genres_list.append(str(g))

    if genres_list:
        info_tag.setGenres(genres_list)

    # Always set Genre1-3 properties for skin chips (max 3)
    # This ensures old values are cleared when list items are recycled
    for i in range(1, 4):
        genre_val = genres_list[i-1] if i <= len(genres_list) else ""
        # Clean up any potential dict-like strings that might cause "{ " errors
        genre_val = str(genre_val).replace('{', '').replace('}', '').strip()
        list_item.setProperty(f'Genre{i}', genre_val)

    # --- Consolidated Rating Logic ---
    rating = meta.get('imdbRating') or meta.get('rating') or meta.get('Rating') or meta.get('stremio_rating') or meta.get('trakt_rating') or ''



    # Fallback to Trakt database for rating if API is empty
    if not rating and media.imdb_id:
        try:
            db = trakt.get_trakt_db()
            if db:
                db_item = None
                if content_type == 'movie':
                    db_item = db.get_movie(media.imdb_id)
                else:
                    db_item = db.get_show(media.imdb_id)

                if db_item and db_item.get('metadata'):
                    m = db_item['metadata']
                    rating = m.get('rating') or m.get('imdbRating') or ''
                    if rating:
                        xbmc.log(f'[AIOStreams] Found database rating for {title}: {rating}', xbmc.LOGDEBUG)
        except:
            pass

    # Filter out dummy/placeholder ratings (like 0.0 or 7.0 for unreleased items)
    rating_value = 0.0
    if rating:
        try:
            rating_value = float(rating)
            # If rating is exactly 7.0 and item is from Cinemate or unreleased, it might be a placeholder
            # But let's be conservative: only filter 0.0 for now, unless we see 7.0 is definitely a dummy.
            # User says 7.0 is everywhere, so it's likely a dummy if the API log showed empty.
            if rating_value == 0:
                rating = ''
            elif rating_value == 7.0:
                # Check if it's a very new item (no released date or in the future)
                released_str = meta.get('released', '')
                if not released_str:
                    xbmc.log(f'[AIOStreams] Filtering out likely dummy 7.0 rating for unreleased item: {title}', xbmc.LOGINFO)
                    rating = ''
        except:
            pass

    # Set properties for skin use
    if rating:
        list_item.setProperty('IMDbRating', f"{rating_value:.1f}")
        list_item.setProperty('TraktRating', f"{rating_value:.1f}")
        info_tag.setRating(rating_value, 0, 'imdb', True)
    else:
        list_item.setProperty('IMDbRating', '')
        list_item.setProperty('TraktRating', '')

    # Always set IMDBNumber and UniqueID for info window compatibility
    if media.imdb_id:
        info_tag.setIMDBNumber(media.imdb_id)
        info_tag.setUniqueID(media.imdb_id, 'imdb')
    # --- End Consolidated Rating Logic ---

    # Cast & Director
    director = meta.get('director') or ''
    list_item.setProperty('Director', str(director))

    cast_data = meta.get('cast', [])
    if isinstance(cast_data, str):
        cast_list = [c.strip() for c in cast_data.split(',') if c.strip()]
    else:
        cast_list = cast_data

    for i in range(1, 4):
        val = cast_list[i-1] if i <= len(cast_list) else ""
        if isinstance(val, dict):
            val = val.get('name') or val.get('label') or ""
        list_item.setProperty(f'Cast{i}', str(val))

    # Rating already set in consolidated block

    # Add debug logging for metadata
    # IMDb Rating, Genre, Premiered and Duration chips support
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
            formatted_date = dependencies.format_date(premiered_date)
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

    # Rating already set in consolidated block

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

    # Check if watched in Trakt and add overlay/properties
    if dependencies.has_modules and trakt.get_access_token():
        trakt_id = media.imdb_id
        if trakt_id:
            try:
                # Use thread-local DB connection for efficiency
                db = trakt.get_trakt_db()
                if db:
                    # Check watched status using local DB directly with IMDb ID
                    is_watched = db.is_imdb_watched(trakt_id, content_type)
                    if is_watched:
                        info_tag.setPlaycount(1)
                        list_item.setProperty('WatchedOverlay', 'indicator_watched.png')
                        list_item.setProperty('watched', 'true')

                    # Check for bookmarks (playback progress)
                    bookmark = db.get_bookmark(imdb_id=trakt_id)
                    if bookmark and bookmark.get('percent_played', 0) > 0:
                        percent = bookmark['percent_played']
                        list_item.setProperty('PercentPlayed', str(int(percent)))
                        info_tag.setPercentPlayed(float(percent))
                        # Set StartOffset for Kodi's internal resume prompt
                        resume_time = bookmark.get('resume_time', 0)
                        if resume_time > 0:
                            list_item.setProperty('StartOffset', str(resume_time))

                    # NEW: Add Trakt ratings from local DB for skin access
                    trakt_data = None
                    if content_type == 'movies':
                        trakt_data = db.get_movie(trakt_id)
                    elif content_type in ['series', 'tvshow']:
                        trakt_data = db.get_show(trakt_id)

                    if trakt_data and trakt_data.get('metadata'):
                        meta_blob = trakt_data['metadata']
                        # Trakt ratings are in the 'rating' field of the metadata blob
                        trakt_rating = meta_blob.get('rating')
                        if trakt_rating:
                            list_item.setProperty('TraktRating', f"{float(trakt_rating):.1f}")

                        # Check for user rating if available
                        user_rating = meta_blob.get('user_rating')
                        if user_rating:
                            list_item.setProperty('TraktUserRating', str(user_rating))
            except Exception as e:
                xbmc.log(f'[AIOStreams] Error setting watched/bookmark/rating status for {dependencies.redact_identifier(trakt_id)}: {e}', xbmc.LOGDEBUG)

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
        metadata_id = media.navigation_id
        cached_clearlogo = dependencies.get_cached_clearlogo_path(content_type, metadata_id) if metadata_id else None

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
            dependencies.ensure_clearlogo_cached(meta, content_type, metadata_id)

    if art:
        list_item.setArt(art)

    # Build context menu based on content type
    context_menu = []

    playback_id = media.playback_id
    trakt_id = media.imdb_id
    title = media.title
    poster = media.poster or ''
    fanart = media.fanart or ''
    # Use the actual clearlogo being used (cached path or URL)
    clearlogo = art.get('clearlogo', meta.get('logo', ''))

    if content_type == 'movie':
        # Movie context menu: Scrape Streams, View Trailer, Mark as Watched, Watchlist
        context_menu.append(('[COLOR lightcoral]Scrape Streams[/COLOR]', f'RunPlugin({dependencies.get_url(action="show_streams", content_type="movie", media_id=playback_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)})'))

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
        if dependencies.has_modules and trakt.get_access_token() and trakt_id:
            db = trakt.get_trakt_db()

            # OPTIMIZATION: Use local DB for Watched status
            is_watched = False
            if db:
                is_watched = db.is_imdb_watched(trakt_id, content_type)

            if is_watched:
                context_menu.append(('[COLOR lightcoral]Mark Movie As Unwatched[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_mark_unwatched", media_type=content_type, imdb_id=trakt_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Movie As Watched[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_mark_watched", media_type=content_type, imdb_id=trakt_id)})'))

            # OPTIMIZATION: Use local DB for Watchlist
            is_in_watchlist = False
            if db:
                is_in_watchlist = db.is_imdb_in_watchlist(trakt_id, content_type)

            if is_in_watchlist:
                context_menu.append(('[COLOR lightcoral]Remove from Watchlist[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_remove_watchlist", media_type=content_type, imdb_id=trakt_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Add to Watchlist[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_add_watchlist", media_type=content_type, imdb_id=trakt_id)})'))

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
        if dependencies.has_modules and trakt.get_access_token() and trakt_id:
            # OPTIMIZATION: Use local DB only
            db = trakt.get_trakt_db()

            # Check if show is fully watched using local DB
            is_watched = False
            if db:
                progress = db.get_imdb_show_progress(trakt_id)
                if progress:
                    aired = progress.get('aired', 0)
                    completed = progress.get('completed', 0)
                    is_watched = aired > 0 and aired == completed

            if is_watched:
                context_menu.append(('[COLOR lightcoral]Mark Show As Unwatched[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_mark_unwatched", media_type=content_type, imdb_id=trakt_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Mark Show As Watched[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_mark_watched", media_type=content_type, imdb_id=trakt_id)})'))

            # Stop Watching (Drop) and Unhide options for shows
            if content_type in ['show', 'series', 'tvshow']:
                context_menu.append(('[COLOR lightcoral]Stop Watching (Drop) Trakt[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_hide_from_progress", media_type="series", imdb_id=trakt_id)})'))
                context_menu.append(('[COLOR lightgreen]Resume Watching (Unhide) Trakt[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_unhide_from_progress", media_type="series", imdb_id=trakt_id)})'))

            # OPTIMIZATION: Use local DB for Watchlist
            is_in_watchlist = False
            # Reuse db from earlier in this block (lines ~1009)
            if db:
                is_in_watchlist = db.is_imdb_in_watchlist(trakt_id, content_type)

            if is_in_watchlist:
                context_menu.append(('[COLOR lightcoral]Remove from Watchlist[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_remove_watchlist", media_type=content_type, imdb_id=trakt_id)})'))
            else:
                context_menu.append(('[COLOR lightcoral]Add to Watchlist[/COLOR]',
                                    f'RunPlugin({dependencies.get_url(action="trakt_add_watchlist", media_type=content_type, imdb_id=trakt_id)})'))

    list_item.addContextMenuItems(context_menu)

    # Check watched status - Already handled by Direct Injection above!
    # No need to call trakt.is_watched again which might hit API
    return list_item
