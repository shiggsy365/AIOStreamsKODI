import xbmc
import xbmcgui
import xbmcvfs
import json
import os
import sys

# Get the skin directory
SKIN_DIR = xbmcvfs.translatePath('special://skin/')
CONFIG_FILE = os.path.join(SKIN_DIR, 'resources', 'widget_config.json')

# Default configuration
DEFAULT_CONFIG = {
    'home': [],
    'tvshows': [],
    'movies': []
}

def load_config():
    """Load widget configuration from JSON file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save widget configuration to JSON file"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_available_catalogs():
    """Get all available catalogs from the plugin"""
    # This will be populated by calling the plugin
    catalogs = []
    
    # Call the plugin to get catalog list
    import xbmcaddon
    try:
        plugin_url = 'plugin://plugin.video.aiostreams/?action=get_all_catalogs'
        result = xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Files.GetDirectory",
            "params": {"directory": plugin_url},
            "id": 1
        }))
        
        result_data = json.loads(result)
        if 'result' in result_data and 'files' in result_data['result']:
            for item in result_data['result']['files']:
                catalogs.append({
                    'label': item.get('label', ''),
                    'path': item.get('file', ''),
                    'type': item.get('filetype', 'unknown')
                })
    except:
        pass
    
    return catalogs

def load_page(page_name):
    """Load catalogs for a specific page"""
    try:
        window = xbmcgui.Window(1111)
        window.setProperty('CurrentPage', page_name)
    except RuntimeError:
        xbmc.log('[AIOStreams] Widget Manager: Window 1111 not available', xbmc.LOGWARNING)
        return
    
    config = load_config()
    current_catalogs = config.get(page_name, [])
    
    # Populate current catalogs list
    current_list = window.getControl(3000)
    current_list.reset()
    for catalog in current_catalogs:
        item = xbmcgui.ListItem(catalog['label'])
        item.setProperty('path', catalog['path'])
        item.setProperty('type', catalog['type'])
        current_list.addItem(item)
    
    # Populate available catalogs list
    available_list = window.getControl(5000)
    available_list.reset()
    all_catalogs = get_available_catalogs()
    for catalog in all_catalogs:
        item = xbmcgui.ListItem(catalog['label'])
        item.setLabel2(catalog['type'])
        item.setProperty('path', catalog['path'])
        item.setProperty('type', catalog['type'])
        available_list.addItem(item)

def move_up():
    """Move selected catalog up in the list"""
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

def move_down():
    """Move selected catalog down in the list"""
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

def remove_catalog():
    """Remove selected catalog from current page"""
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

def add_catalog():
    """Add selected catalog from available list to current page"""
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

def save_and_exit():
    """Save configuration and reload skin"""
    xbmc.executebuiltin('ReloadSkin()')

# Main entry point
if __name__ == '__main__':
    if len(sys.argv) > 1:
        action = sys.argv[1]
        
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
