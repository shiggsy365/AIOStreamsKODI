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

# Default configuration - matches widget_config_loader.py
DEFAULT_CONFIG = {
    'home': [
        {
            'label': 'Trakt Next Up',
            'path': 'plugin://plugin.video.aiostreams/?action=trakt_next_up',
            'type': 'series',
            'is_trakt': True
        }
    ],
    'tvshows': [
        {
            'label': 'Trakt Watchlist Series',
            'path': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=shows',
            'type': 'series',
            'is_trakt': True
        }
    ],
    'movies': [
        {
            'label': 'Trakt Watchlist Movies',
            'path': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=movies',
            'type': 'movie',
            'is_trakt': True
        }
    ],
    'version': 2  # Config version for future migrations
}

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[AIOStreams] [WidgetManager] {msg}', level)

def load_config():
    """
    Load widget configuration from JSON file.
    Forces reset to defaults if version is old or missing.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            # Check version - if old or missing, force reset to defaults
            if config.get('version') != 2:
                log('Old config version detected, resetting to defaults', xbmc.LOGINFO)
                save_config(DEFAULT_CONFIG.copy())
                return DEFAULT_CONFIG.copy()
            
            return config
        except Exception as e:
            log(f'Error loading config: {e}', xbmc.LOGERROR)
            save_config(DEFAULT_CONFIG.copy())
            return DEFAULT_CONFIG.copy()
    
    log(f'Config file not found, creating with defaults', xbmc.LOGINFO)
    save_config(DEFAULT_CONFIG.copy())
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
    xbmc.sleep(100)

    window = None
    try:
        # Try finding the window by ID first
        window = xbmcgui.Window(1111)
        # Verify it's actually our window (this will fail if not active)
        test_control = window.getControl(3000)
        log(f'Found window 1111, control 3000 exists: {test_control is not None}')
    except Exception as first_error:
        log(f'Window 1111 not accessible: {first_error}', xbmc.LOGDEBUG)
        try:
            # Fallback to current window dialog
            current_dialog_id = xbmcgui.getCurrentWindowDialogId()
            log(f'Trying current dialog ID: {current_dialog_id}')
            if current_dialog_id == 1111:
                window = xbmcgui.Window(current_dialog_id)
                window.getControl(3000)  # Verify it works
                log('Successfully using current dialog window')
            else:
                log(f'Current dialog ID {current_dialog_id} is not our widget manager', xbmc.LOGERROR)
                return
        except Exception as e:
            log(f'Critical: Could not access window: {e}', xbmc.LOGERROR)
            log('Widget manager window is not open', xbmc.LOGERROR)
            return

    try:
        # Set properties on both the dialog window and home window for accessibility
        window.setProperty('CurrentPage', page_name)
        # Set a user-friendly page name for display
        page_display_names = {
            'home': 'Home',
            'tvshows': 'TV Shows',
            'movies': 'Movies'
        }
        display_name = page_display_names.get(page_name, page_name.capitalize())
        window.setProperty('CurrentPageName', display_name)

        # Also set on home window so dialog can access it
        home_window = xbmcgui.Window(10000)
        home_window.setProperty('WidgetManager.CurrentPage', page_name)
        home_window.setProperty('WidgetManager.CurrentPageName', display_name)

        log(f'Set window properties: CurrentPage={page_name}, CurrentPageName={display_name}')
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

        # Check if this is a placeholder item
        if current_list.size() > 0:
            item = current_list.getSelectedItem()
            if item.getProperty('is_placeholder') == 'true':
                log('Cannot move placeholder item')
                return

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

        # Check if this is a placeholder item
        if current_list.size() > 0:
            item = current_list.getSelectedItem()
            if item.getProperty('is_placeholder') == 'true':
                log('Cannot move placeholder item')
                return

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

        # Check if this is a placeholder item
        if current_list.size() > 0:
            item = current_list.getSelectedItem()
            if item.getProperty('is_placeholder') == 'true':
                log('Cannot remove placeholder item')
                return

        page_name = window.getProperty('CurrentPage')
        config = load_config()
        catalogs = config.get(page_name, [])

        if pos >= 0 and pos < len(catalogs):
            removed_label = catalogs[pos].get('label', 'Unknown')
            log(f'Removing catalog: {removed_label}')
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

        log(f'add_catalog: Selected position: {pos}')

        if pos >= 0:
            item = available_list.getSelectedItem()
            catalog = {
                'label': item.getLabel(),
                'path': item.getProperty('path'),
                'type': item.getProperty('type'),
                'is_trakt': item.getProperty('is_trakt') == 'true'
            }

            log(f'add_catalog: Adding catalog: {catalog["label"]} (type: {catalog["type"]}, path: {catalog["path"][:50]}...)')

            page_name = window.getProperty('CurrentPage')
            log(f'add_catalog: Current page: {page_name}')

            config = load_config()
            catalogs = config.get(page_name, [])
            log(f'add_catalog: Current page has {len(catalogs)} catalogs before adding')

            # Add to end of list
            catalogs.append(catalog)
            config[page_name] = catalogs
            save_config(config)
            log(f'add_catalog: Saved config with {len(catalogs)} catalogs for {page_name}')

            # Reload
            load_page(page_name)
            log('add_catalog: Reloaded page')
    except Exception as e:
        log(f'Error in add_catalog: {e}', xbmc.LOGERROR)
        import traceback
        log(traceback.format_exc(), xbmc.LOGERROR)

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
                'movies': [],
                'version': 2
            }
            save_config(config)

            # Try to reload current page to show empty state
            try:
                window = xbmcgui.Window(1111)
                page_name = window.getProperty('CurrentPage')
                if page_name:
                    load_page(page_name)
                else:
                    load_page('home')
            except Exception as e:
                log(f'Could not reload page after clearing: {e}', xbmc.LOGDEBUG)
                # Window might not be available, but config is already saved
                pass

            log('All catalogs cleared')
    except Exception as e:
        log(f'Error in clear_all: {e}', xbmc.LOGERROR)


def reset_to_defaults():
    """Reset widget configuration to defaults"""
    try:
        dialog = xbmcgui.Dialog()
        if dialog.yesno('Reset to Defaults',
                       'This will reset all pages to default widgets:',
                       'Home: Trakt Next Up | Movies: Trakt Watchlist Movies | TV Shows: Trakt Watchlist Series',
                       'Are you sure?'):
            log('Resetting all widgets to defaults')
            save_config(DEFAULT_CONFIG.copy())
            
            # Reload current page
            try:
                window = xbmcgui.Window(1111)
                page_name = window.getProperty('CurrentPage')
                if page_name:
                    load_page(page_name)
                else:
                    load_page('home')
            except Exception as e:
                log(f'Could not reload page after reset: {e}', xbmc.LOGDEBUG)
            
            log('Reset to defaults complete')
    except Exception as e:
        log(f'Error in reset_to_defaults: {e}', xbmc.LOGERROR)

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
        elif action == 'reset_to_defaults':
            reset_to_defaults()
        elif action == 'save_and_exit':
            save_and_exit()
