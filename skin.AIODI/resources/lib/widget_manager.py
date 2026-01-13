import xbmc
import xbmcgui
import xbmcvfs
import json
import os
import sys

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
    plugin_url = 'plugin://plugin.video.aiostreams/?action=get_all_catalogs'
    
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
                catalogs.append({
                    'label': item.get('label', 'Unknown'),
                    'path': item.get('file', ''),
                    'type': item.get('filetype', 'unknown') or item.get('filetype', 'directory')
                })
        else:
            log(f'JSON-RPC call failed or returned no files: {result}', xbmc.LOGERROR)
    except Exception as e:
        log(f'Exception in get_available_catalogs: {e}', xbmc.LOGERROR)
    
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
    log(f'Current catalogs in config: {len(current_catalogs)}')
    
    # Populate current catalogs list
    try:
        current_list = window.getControl(3000)
        current_list.reset()
        for catalog in current_catalogs:
            item = xbmcgui.ListItem(catalog.get('label', 'Unknown'))
            item.setProperty('path', catalog.get('path', ''))
            item.setProperty('type', catalog.get('type', 'unknown'))
            current_list.addItem(item)
    except Exception as e:
        log(f'Error populating current_list (3000): {e}', xbmc.LOGERROR)
    
    # Populate available catalogs list
    try:
        available_list = window.getControl(5000)
        available_list.reset()
        all_catalogs = get_available_catalogs()
        log(f'Total available catalogs: {len(all_catalogs)}')
        for catalog in all_catalogs:
            item = xbmcgui.ListItem(catalog.get('label', 'Unknown'))
            item.setLabel2(catalog.get('type', ''))
            item.setProperty('path', catalog.get('path', ''))
            item.setProperty('type', catalog.get('type', 'unknown'))
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
                'type': item.getProperty('type')
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
        elif action == 'save_and_exit':
            save_and_exit()
