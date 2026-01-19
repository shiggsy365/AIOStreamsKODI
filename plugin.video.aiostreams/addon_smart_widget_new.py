def smart_widget():
    """
    Dynamic widget content generator using widget_config.json.

    URL Parameters:
        index: Widget index (0, 1, 2, ...)
        content_type: 'series', 'movie', or 'home'

    Returns:
        Content from configured widget at specified index
    """
    params = dict(parse_qsl(sys.argv[2][1:]))
    index = int(params.get('index', 0))
    content_type = params.get('content_type', 'movie')

    # Optimization: If Search Dialog (1112) or Info Dialog (12003) OR ANY MODAL is open, skip background widget loading
    if xbmc.getCondVisibility('Window.IsVisible(1112)') or xbmc.getCondVisibility('Window.IsVisible(12003)') or xbmc.getCondVisibility('System.HasModalDialog'):
        xbmc.log(f'[AIOStreams] smart_widget: Skipping background load (Dialog Open) - index={index}', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmc.log(f'[AIOStreams] smart_widget: index={index}, content_type={content_type}', xbmc.LOGINFO)
    
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
        widget_type = widget.get('type', 'unknown')
        
        xbmc.log(f'[AIOStreams] smart_widget: Loading "{label}" (type: {widget_type})', xbmc.LOGINFO)
        
        # Parse the widget path
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(path)
        widget_params = parse_qs(parsed.query)
        
        # Extract action
        action = widget_params.get('action', [None])[0]
        
        if not action:
            xbmc.log(f'[AIOStreams] smart_widget: No action in widget path: {path}', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(HANDLE)
            return
        
        # Handle different actions
        if action == 'trakt_next_up':
            return trakt_next_up()
        
        elif action == 'trakt_watchlist':
            media_type = widget_params.get('media_type', ['movies'])[0]
            return trakt_watchlist({'media_type': media_type})
        
        elif action == 'catalog':
            # Handle catalog action
            catalog_id = widget_params.get('catalog_id', [None])[0]
            if not catalog_id:
                xbmc.log(f'[AIOStreams] smart_widget: No catalog_id in path: {path}', xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(HANDLE)
                return
            
            # Set plugin metadata
            xbmcplugin.setPluginCategory(HANDLE, label)
            xbmcplugin.setContent(HANDLE, 'tvshows' if content_type == 'series' else 'movies')
            
            # Prime database cache
            if HAS_MODULES:
                trakt.prime_database_cache(content_type)
            
            # Check cache first (15-minute TTL)
            cache_key = f'widget_{content_type}_{catalog_id}_all'
            catalog_data = _get_cached_widget(cache_key)
            
            if catalog_data is None:
                # Fetch catalog content
                catalog_data = get_catalog(content_type, catalog_id, genre=None, skip=0)
                
                # Cache it if valid
                if catalog_data and 'metas' in catalog_data:
                    _cache_widget(cache_key, catalog_data)
            
            if not catalog_data or 'metas' not in catalog_data:
                xbmc.log(f'[AIOStreams] smart_widget: No content in catalog {catalog_id}', xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(HANDLE)
                return
            
            # Add items
            for meta in catalog_data['metas']:
                item_id = meta.get('id')
                if not item_id:
                    continue
                
                # For series: navigate to show (will then go to seasons/episodes)
                # For movies: direct play
                if content_type == 'series':
                    url = get_url(action='show_seasons', meta_id=item_id)
                    is_folder = True
                else:
                    url = get_url(action='show_streams', content_type='movie', media_id=item_id,
                                title=meta.get('name', ''), poster=meta.get('poster', ''),
                                year=meta.get('releaseInfo', ''), imdb_id=meta.get('imdb_id', ''))
                    is_folder = False
                
            
                li = create_list_item(meta, content_type)
                xbmcplugin.addDirectoryItem(HANDLE, url, li, is_folder)
            
            xbmcplugin.endOfDirectory(HANDLE)
            return
        
        else:
            xbmc.log(f'[AIOStreams] smart_widget: Unknown action "{action}"', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(HANDLE)
            return
    
    except Exception as e:
        xbmc.log(f'[AIOStreams] smart_widget: Error loading widget: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(HANDLE)
