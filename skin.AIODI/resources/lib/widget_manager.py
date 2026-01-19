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
    'version': 2
}

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[AIOStreams] [WidgetManager] {msg}', level)

class WidgetManager(xbmcgui.WindowXMLDialog):
    def __init__(self, strXMLname, strFallbackPath, strDefaultName, forceFallback=0):
        super().__init__(strXMLname, strFallbackPath, strDefaultName, forceFallback)
        self.current_page = 'home'
        self.config = {}

    def onInit(self):
        log("WidgetManager onInit")
        self.load_config()
        self.load_page(self.current_page)

    def onAction(self, action):
        # Capture Context Menu (117) and Right Click (101)
        if action.getId() in [117, 101]:
            focus_id = self.getFocusId()
            log(f"Context menu action triggered on control {focus_id}")
            if focus_id == 3000: # Current Catalogs
                self.show_current_context_menu()
            elif focus_id == 5000: # Available Catalogs
                self.show_available_context_menu()
        
        # Capture Back/Previous Menu to close
        elif action.getId() in [10, 92]:
            self.save_and_exit()

    def onClick(self, controlId):
        log(f"onClick: {controlId}")
        if controlId == 2001: # Home
            self.load_page('home')
        elif controlId == 2002: # TV Shows
            self.load_page('tvshows')
        elif controlId == 2003: # Movies
            self.load_page('movies')
        elif controlId == 6000: # Close
            self.save_and_exit()
        elif controlId == 6001: # Clear All
            self.clear_all()
        elif controlId == 6002: # Reset Defaults
            self.reset_to_defaults()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
                
                if self.config.get('version') != 2:
                    log('Old config version, resetting')
                    self.config = DEFAULT_CONFIG.copy()
                    self.save_config()
            except Exception as e:
                log(f'Error loading config: {e}', xbmc.LOGERROR)
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()

    def save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            log("Config saved")
        except Exception as e:
            log(f'Error saving config: {e}', xbmc.LOGERROR)

    def load_page(self, page_name):
        self.current_page = page_name
        
        # Set window properties for UI
        page_display_names = {'home': 'Home', 'tvshows': 'TV Shows', 'movies': 'Movies'}
        display_name = page_display_names.get(page_name, page_name.capitalize())
        
        # Set on home window so include conditions might work if they check 10000
        xbmcgui.Window(10000).setProperty('WidgetManager.CurrentPageName', display_name)
        
        # Populate current list (3000)
        current_list = self.getControl(3000)
        current_list.reset()
        
        items = self.config.get(page_name, [])
        if not items:
            placeholder = xbmcgui.ListItem('[I]No catalogs added[/I]')
            placeholder.setLabel2('[I]Use ← to add[/I]')
            placeholder.setProperty('is_placeholder', 'true')
            current_list.addItem(placeholder)
        else:
            for item_data in items:
                item = xbmcgui.ListItem(item_data.get('label', 'Unknown'))
                item.setLabel2(item_data.get('type', 'unknown').capitalize())
                item.setProperty('path', item_data.get('path', ''))
                item.setProperty('type', item_data.get('type', 'unknown'))
                item.setProperty('is_trakt', str(item_data.get('is_trakt', False)).lower())
                current_list.addItem(item)
                
        # Populate available list (5000)
        # For efficiency, we might cache this, but for now fetch every page load for simplicity
        self.populate_available_list()

    def populate_available_list(self):
        available_list = self.getControl(5000)
        available_list.reset()
        
        # We need to fetch catalogs or use cached ones. 
        # For simplicity, I'll copy the logic from original script but inside class
        
        # Hardcoded Trakt
        trakt_widgets = [
            {'label': 'Trakt Next Up', 'path': 'plugin://plugin.video.aiostreams/?action=trakt_next_up', 'type': 'series', 'is_trakt': True},
            {'label': 'Trakt Watchlist Movies', 'path': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=movies', 'type': 'movie', 'is_trakt': True},
            {'label': 'Trakt Watchlist Series', 'path': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=shows', 'type': 'series', 'is_trakt': True}
        ]
        
        for w in trakt_widgets:
            item = xbmcgui.ListItem(w['label'])
            item.setLabel2(w['type'].capitalize())
            item.setProperty('path', w['path'])
            item.setProperty('type', w['type'])
            item.setProperty('is_trakt', 'true')
            available_list.addItem(item)
            
        # Fetch from plugin
        plugin_url = 'plugin://plugin.video.aiostreams/?action=get_folder_browser_catalogs'
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
                 for f in result_data['result']['files']:
                     item = xbmcgui.ListItem(f.get('label'))
                     path = f.get('file')
                     # Try parse type
                     try:
                         parsed = urlparse(path)
                         params = parse_qs(parsed.query)
                         ctype = params.get('content_type', ['unknown'])[0]
                     except:
                         ctype = 'unknown'
                     
                     item.setLabel2(ctype.capitalize())
                     item.setProperty('path', path)
                     item.setProperty('type', ctype)
                     item.setProperty('is_trakt', 'false')
                     available_list.addItem(item)
        except Exception as e:
            log(f"Error fetching catalogs: {e}", xbmc.LOGERROR)

    def show_current_context_menu(self):
        list_ctrl = self.getControl(3000)
        pos = list_ctrl.getSelectedPosition()
        if pos < 0: return
        
        item = list_ctrl.getSelectedItem()
        if item.getProperty('is_placeholder') == 'true': return
        
        options = ['Move Up', 'Move Down', 'Remove from Page']
        choice = xbmcgui.Dialog().contextmenu(options)
        
        if choice == 0: self.move_item(pos, -1)
        elif choice == 1: self.move_item(pos, 1)
        elif choice == 2: self.remove_item(pos)

    def show_available_context_menu(self):
        list_ctrl = self.getControl(5000)
        pos = list_ctrl.getSelectedPosition()
        if pos < 0: return
        
        options = [f"Add to {self.current_page.capitalize()}"]
        choice = xbmcgui.Dialog().contextmenu(options)
        
        if choice == 0: self.add_item(list_ctrl.getSelectedItem())

    def move_item(self, pos, direction):
        items = self.config.get(self.current_page, [])
        new_pos = pos + direction
        if 0 <= new_pos < len(items):
            items[pos], items[new_pos] = items[new_pos], items[pos]
            self.config[self.current_page] = items
            self.save_config()
            self.load_page(self.current_page)
            self.getControl(3000).selectItem(new_pos)

    def remove_item(self, pos):
        items = self.config.get(self.current_page, [])
        if 0 <= pos < len(items):
            items.pop(pos)
            self.config[self.current_page] = items
            self.save_config()
            self.load_page(self.current_page)
            
    def add_item(self, list_item):
        catalog = {
            'label': list_item.getLabel(),
            'path': list_item.getProperty('path'),
            'type': list_item.getProperty('type'),
            'is_trakt': list_item.getProperty('is_trakt') == 'true'
        }
        
        items = self.config.get(self.current_page, [])
        items.append(catalog)
        self.config[self.current_page] = items
        self.save_config()
        self.load_page(self.current_page)
        xbmcgui.Dialog().notification('Widget Manager', f'Added to {self.current_page}', xbmcgui.NOTIFICATION_INFO, 2000)

    def clear_all(self):
        if xbmcgui.Dialog().yesno('Clear All', 'Are you sure you want to remove all widgets?'):
            self.config = {'home': [], 'tvshows': [], 'movies': [], 'version': 2}
            self.save_config()
            self.load_page(self.current_page)

    def reset_to_defaults(self):
        if xbmcgui.Dialog().yesno('Reset Defaults', 'Reset all widgets to default configuration?'):
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()
            self.load_page(self.current_page)

    def save_and_exit(self):
        # Apply window properties immediately for headers
        # This prevents race condition where skin loads before widget content
        log("Applying widget header properties...")
        
        # Mapping matches Home.xml conventions
        page_properties = {
            'home': 'WidgetLabel_Home_{}',
            'movies': 'movie_catalog_{}_name',
            'tvshows': 'series_catalog_{}_name'
        }
        
        for page, fmt in page_properties.items():
            widgets = self.config.get(page, [])
            for i, widget in enumerate(widgets):
                label = widget.get('label', '')
                prop_name = fmt.format(i)
                xbmcgui.Window(10000).setProperty(prop_name, label)
                # Also set "old" style just in case
                xbmcgui.Window(10000).setProperty(f'{page}_widget_{i}_name', label)
                log(f"Set property {prop_name} = {label}")
                
            # Clear remaining slots (up to 20) to avoid ghost headers
            for i in range(len(widgets), 20):
                prop_name = fmt.format(i)
                xbmcgui.Window(10000).clearProperty(prop_name)
                xbmcgui.Window(10000).clearProperty(f'{page}_widget_{i}_name')

        # Update reload token to force widget refresh
        import time
        token = str(int(time.time()))
        xbmc.executebuiltin(f'Skin.SetString(WidgetReloadToken, {token})')
        
        # DEBUG: Dump config to workspace for verification
        try:
            dump_path = '/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/widget_dump.json'
            with open(dump_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            log(f"Debug config dumped to {dump_path}")
        except Exception as e:
            log(f"Failed to dump debug config: {e}")

        self.close()
        xbmc.executebuiltin('ReloadSkin()')

if __name__ == '__main__':
    ui = WidgetManager('Custom_ModifyLists.xml', 'special://skin/', 'Default')
    ui.doModal()
    del ui
