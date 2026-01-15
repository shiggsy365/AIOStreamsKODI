import xbmc
import xbmcgui
import xbmcvfs
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

# Get the addon data directory (preferred for configuration)
ADDON_DATA_DIR = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/')
CONFIG_FILE = os.path.join(ADDON_DATA_DIR, 'widget_config.json')

# Default configuration
DEFAULT_CONFIG = {
    'home': [],
    'tvshows': [],
    'movies': []
}

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[AIOStreams] [WidgetManager] {msg}', level)

def load_config():
    """Load widget configuration from JSON file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            log(f'Error loading config: {e}', xbmc.LOGERROR)
            return DEFAULT_CONFIG.copy()
    log(f'Config file not found at {CONFIG_FILE}, using defaults', xbmc.LOGDEBUG)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save widget configuration to JSON file"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        log(f'Config saved to {CONFIG_FILE}')
    except Exception as e:
        log(f'Error saving config: {e}', xbmc.LOGERROR)

def get_available_catalogs():
    """Get all available catalogs from the plugin via JSON-RPC"""
    catalogs = []

    # Add hardcoded Trakt widgets first (shown in yellow)
    trakt_widgets = [
        {
            'label': 'Trakt Next Up',
            'path': 'plugin://plugin.video.aiostreams/?action=trakt_next_up',
            'type': 'series',
            'is_trakt': True
        },
        {
            'label': 'Trakt Watchlist Movies',
            'path': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=movies',
            'type': 'movie',
            'is_trakt': True
        },
        {
            'label': 'Trakt Watchlist Series',
            'path': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=shows',
            'type': 'series',
            'is_trakt': True
        }
    ]
    catalogs.extend(trakt_widgets)
    log(f'Added {len(trakt_widgets)} hardcoded Trakt widgets')

    # Fetch AIOStreams catalogs from the plugin
    plugin_url = 'plugin://plugin.video.aiostreams/?action=get_folder_browser_catalogs'
    log(f'Fetching available catalogs from {plugin_url}...')
    try:
        rpc_query = {
            "jsonrpc": "2.0",
            "method": "Files.GetDirectory",
            "params": {"directory": plugin_url, "media": "video"},
            "id": 1
        }
        result = xbmc.executeJSONRPC(json.dumps(rpc_query))
        result_data = json.loads(result)

        if 'result' in result_data and 'files' in result_data['result']:
            files = result_data['result']['files']
            log(f'Received {len(files)} catalogs from plugin')
            for item in files:
                # Extract content_type from URL parameters
                url = item.get('file', '')
                content_type = 'unknown'
                try:
                    parsed = urlparse(url)
                    params = parse_qs(parsed.query)
                    content_type = params.get('content_type', ['unknown'])[0]
                except Exception as e:
                    log(f'Error parsing URL {url}: {e}', xbmc.LOGDEBUG)

                catalogs.append({
                    'label': item.get('label', 'Unknown'),
                    'path': url,
                    'type': content_type,
                    'is_trakt': False
                })
        else:
            log(f'JSON-RPC call failed or returned no files: {result}', xbmc.LOGERROR)
    except Exception as e:
        log(f'Exception in get_available_catalogs: {e}', xbmc.LOGERROR)

    log(f'Total available catalogs: {len(catalogs)}')
    return catalogs

def load_page(page_name):
    """Load catalogs for a specific page"""
    log(f'Loading page: {page_name}')
    
    # Give the window a moment to fully initialize
    xbmc.sleep(200)
    
    window = None
    try:
        # Try finding the window by ID first
        window = xbmcgui.Window(1111)
        # Verify it's actually our window (this will fail if not active)
        window.getControl(3000)
        log('Found window 1111')
    except:
        try:
            # Fallback to current window
            window = xbmcgui.getCurrentWindowDialogId()
            log(f'Fallback: Using current window dialog ID {window}')
            window = xbmcgui.Window(window)
        except Exception as e:
            log(f'Critical: Could not access window: {e}', xbmc.LOGERROR)
            return

    try:
        window.setProperty('CurrentPage', page_name)
    except Exception as e:
        log(f'Error setting property on window: {e}', xbmc.LOGERROR)
        return
    
    config = load_config()
    current_catalogs = config.get(page_name, [])
    log(f'Current catalogs for page "{page_name}": {len(current_catalogs)} items')
    log(f'Config content: {config}')
    
    # Populate current catalogs list
    try:
        current_list = window.getControl(3000)
        current_list.reset()
        log(f'Populating current list with {len(current_catalogs)} catalogs')

        if len(current_catalogs) == 0:
            # Add a placeholder item when the list is empty
            placeholder = xbmcgui.ListItem('[I]No catalogs added[/I]')
            placeholder.setLabel2('[I]Use ← to add[/I]')
            placeholder.setProperty('is_trakt', 'false')
            placeholder.setProperty('is_used', 'false')
            placeholder.setProperty('is_placeholder', 'true')
            current_list.addItem(placeholder)
            log('Added placeholder item to empty current list')
        else:
            for i, catalog in enumerate(current_catalogs):
                label = catalog.get('label', 'Unknown')
                log(f'  [{i}] Adding catalog: {label}')
                item = xbmcgui.ListItem(label)
                # Capitalize the type for better display
                content_type = catalog.get('type', 'unknown')
                display_type = content_type.capitalize() if content_type != 'unknown' else ''
                item.setLabel2(display_type)
                item.setProperty('path', catalog.get('path', ''))
                item.setProperty('type', content_type)
                item.setProperty('is_trakt', 'true' if catalog.get('is_trakt', False) else 'false')
                # Set is_used to false for current items (not used by color variables, but set for consistency)
                item.setProperty('is_used', 'false')
                log(f'    Label: {label}, Label2: {display_type}, is_trakt: {item.getProperty("is_trakt")}')
                current_list.addItem(item)
        log(f'Current list populated successfully with {current_list.size()} items')
    except Exception as e:
        log(f'Error populating current_list (3000): {e}', xbmc.LOGERROR)
    
    # Populate available catalogs list
    try:
        available_list = window.getControl(5000)
        available_list.reset()
        all_catalogs = get_available_catalogs()
        log(f'Total available catalogs: {len(all_catalogs)}')

        # Build a set of paths that are currently in use on ANY page
        used_paths = set()
        for page in ['home', 'tvshows', 'movies']:
            page_catalogs = config.get(page, [])
            for cat in page_catalogs:
                used_paths.add(cat.get('path', ''))

        log(f'Found {len(used_paths)} catalogs in use across all pages')

        for catalog in all_catalogs:
            item = xbmcgui.ListItem(catalog.get('label', 'Unknown'))
            # Capitalize the type for better display (e.g., "movie" -> "Movie", "series" -> "Series")
            content_type = catalog.get('type', 'unknown')
            display_type = content_type.capitalize() if content_type != 'unknown' else ''
            item.setLabel2(display_type)
            item.setProperty('path', catalog.get('path', ''))
            item.setProperty('type', content_type)
            item.setProperty('is_trakt', 'true' if catalog.get('is_trakt', False) else 'false')
            # Mark if this catalog is currently in use on any page
            is_used = catalog.get('path', '') in used_paths
            item.setProperty('is_used', 'true' if is_used else 'false')
            available_list.addItem(item)
    except Exception as e:
        log(f'Error populating available_list (5000): {e}', xbmc.LOGERROR)

def move_up():
    """Move selected catalog up in the list"""
    try:
        window = xbmcgui.Window(1111)
        current_list = window.getControl(3000)
        pos = current_list.getSelectedPosition()
        
        if pos > 0:
            page_name = window.getProperty('CurrentPage')
            config = load_config()
            catalogs = config.get(page_name, [])
            
            # Swap positions
            catalogs[pos], catalogs[pos-1] = catalogs[pos-1], catalogs[pos]
            config[page_name] = catalogs
            save_config(config)
            
            # Reload
            load_page(page_name)
            current_list.selectItem(pos-1)
    except Exception as e:
        log(f'Error in move_up: {e}', xbmc.LOGERROR)

def move_down():
    """Move selected catalog down in the list"""
    try:
        window = xbmcgui.Window(1111)
        current_list = window.getControl(3000)
        pos = current_list.getSelectedPosition()
        
        page_name = window.getProperty('CurrentPage')
        config = load_config()
        catalogs = config.get(page_name, [])
        
        if pos < len(catalogs) - 1:
            # Swap positions
            catalogs[pos], catalogs[pos+1] = catalogs[pos+1], catalogs[pos]
            config[page_name] = catalogs
            save_config(config)
            
            # Reload
            load_page(page_name)
            current_list.selectItem(pos+1)
    except Exception as e:
        log(f'Error in move_down: {e}', xbmc.LOGERROR)

def remove_catalog():
    """Remove selected catalog from current page"""
    try:
        window = xbmcgui.Window(1111)
        current_list = window.getControl(3000)
        pos = current_list.getSelectedPosition()
        
        page_name = window.getProperty('CurrentPage')
        config = load_config()
        catalogs = config.get(page_name, [])
        
        if pos >= 0 and pos < len(catalogs):
            catalogs.pop(pos)
            config[page_name] = catalogs
            save_config(config)
            
            # Reload
            load_page(page_name)
            if pos > 0:
                current_list.selectItem(pos-1)
            elif len(catalogs) > 0:
                current_list.selectItem(0)
    except Exception as e:
        log(f'Error in remove_catalog: {e}', xbmc.LOGERROR)

def add_catalog():
    """Add selected catalog from available list to current page"""
    try:
        window = xbmcgui.Window(1111)
        available_list = window.getControl(5000)
        pos = available_list.getSelectedPosition()

        if pos >= 0:
            item = available_list.getSelectedItem()
            catalog = {
                'label': item.getLabel(),
                'path': item.getProperty('path'),
                'type': item.getProperty('type'),
                'is_trakt': item.getProperty('is_trakt') == 'true'
            }

            page_name = window.getProperty('CurrentPage')
            config = load_config()
            catalogs = config.get(page_name, [])

            # Add to end of list
            catalogs.append(catalog)
            config[page_name] = catalogs
            save_config(config)

            # Reload
            load_page(page_name)
    except Exception as e:
        log(f'Error in add_catalog: {e}', xbmc.LOGERROR)

def clear_all():
    """Clear all catalogs from all pages"""
    try:
        # Show confirmation dialog
        dialog = xbmcgui.Dialog()
        if dialog.yesno('Clear All Catalogs',
                       'This will remove all catalogs from Home, TV Shows, and Movies pages.',
                       'Are you sure?'):
            log('Clearing all catalogs from all pages')
            config = {
                'home': [],
                'tvshows': [],
                'movies': []
            }
            save_config(config)

            # Reload current page to show empty state
            window = xbmcgui.Window(1111)
            page_name = window.getProperty('CurrentPage')
            if page_name:
                load_page(page_name)
            else:
                load_page('home')

            log('All catalogs cleared')
    except Exception as e:
        log(f'Error in clear_all: {e}', xbmc.LOGERROR)

def save_and_exit():
    """Save configuration and reload skin"""
    log('Saving and exiting...')
    xbmc.executebuiltin('ReloadSkin()')

# Main entry point
if __name__ == '__main__':
    if len(sys.argv) > 1:
        action = sys.argv[1]
        log(f'Action: {action} with args: {sys.argv[2:]}')
        
        if action == 'load_page' and len(sys.argv) > 2:
            load_page(sys.argv[2])
        elif action == 'move_up':
            move_up()
        elif action == 'move_down':
            move_down()
        elif action == 'remove_catalog':
            remove_catalog()
        elif action == 'add_catalog':
            add_catalog()
        elif action == 'clear_all':
            clear_all()
        elif action == 'save_and_exit':
            save_and_exit()
