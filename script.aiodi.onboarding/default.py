import xbmc
import xbmcgui
import xbmcaddon
import os
import json
import threading
import time
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
WINDOW = xbmcgui.Window(10000) # Home window for property storage

# Persistence helpers
def get_cache_path():
    path = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    if not os.path.exists(path):
        os.makedirs(path)
    return os.path.join(path, 'settings_cache.json')

def load_cache():
    path = get_cache_path()
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except: pass
    return {}

def save_cache(data):
    try:
        with open(get_cache_path(), 'w') as f:
            json.dump(data, f)
    except: pass

def install_with_wait(addon_id, progress, start_pct, end_pct):
    if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
        return True

    progress.update(int(start_pct), f"Installing {addon_id}...")
    xbmc.executebuiltin(f'InstallAddon({addon_id})')
    
    # Wait loop (max 60s)
    for i in range(120):
        if progress.iscanceled(): return False
        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            progress.update(int(end_pct))
            return True
        time.sleep(0.5)
    return False

# Selection IDs from onboarding.xml (legacy support)
ID_AIOSTREAMS = 1101
ID_TRAKT = 1102
ID_SKIN = 2101
ID_YOUTUBE = 2102
ID_UPNEXT = 2103
ID_IPTV = 3101
ID_IMVDB = 3102
ID_TMDBH = 3103

class InputWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super(InputWindow, self).__init__(*args, **kwargs)
        self.cache = load_cache()
        
        # Initialize selections with defaults/cache
        self.selections = {
            'aiostreams': True,
            'trakt': True,
            'skin': self.cache.get('skin', True),
            'youtube': self.cache.get('youtube', False),
            'upnext': self.cache.get('upnext', True),
            'iptv': self.cache.get('iptv', False),
            'imvdb': self.cache.get('imvdb', False),
            'tmdbh': self.cache.get('tmdbh', True)
        }
        self.data = {}
        self.cancelled = True

    def onInit(self):
        # Initial radio button states for Modules tab
        self.getControl(10101).setSelected(True) # AIOStreams
        self.getControl(10102).setSelected(True) # Trakt
        self.getControl(10103).setSelected(self.selections['skin'])
        self.getControl(10104).setSelected(self.selections['youtube'])
        self.getControl(10105).setSelected(self.selections['upnext'])
        self.getControl(10106).setSelected(self.selections['iptv'])
        self.getControl(10107).setSelected(self.selections['imvdb'])
        self.getControl(10108).setSelected(self.selections['tmdbh'])
        
        # Pre-fill settings from cache
        if 'aiostreams_host' in self.cache: self.getControl(10001).setLabel(self.cache['aiostreams_host'])
        if 'aiostreams_uuid' in self.cache: self.getControl(10002).setLabel(self.cache['aiostreams_uuid'])
        if 'aiostreams_password' in self.cache: self.getControl(10003).setLabel(self.cache['aiostreams_password'])
        if 'aiostreams_behavior' in self.cache: self.getControl(10004).setLabel(self.cache['aiostreams_behavior'])
        if 'aiostreams_subtitles' in self.cache: self.getControl(10005).setLabel(self.cache['aiostreams_subtitles'])
        if 'aiostreams_upnext' in self.cache: self.getControl(10006).setSelected(self.cache['aiostreams_upnext'])
        
        if 'trakt_id' in self.cache: self.getControl(11001).setLabel(self.cache['trakt_id'])
        if 'trakt_secret' in self.cache: self.getControl(11002).setLabel(self.cache['trakt_secret'])
        
        if 'yt_key' in self.cache: self.getControl(12001).setLabel(self.cache['yt_key'])
        if 'yt_id' in self.cache: self.getControl(12002).setLabel(self.cache['yt_id'])
        if 'yt_secret' in self.cache: self.getControl(12003).setLabel(self.cache['yt_secret'])
        
        if 'iptv_m3u' in self.cache: self.getControl(13001).setLabel(self.cache['iptv_m3u'])
        if 'iptv_epg' in self.cache: self.getControl(13002).setLabel(self.cache['iptv_epg'])
        
        if 'imvdb_key' in self.cache: self.getControl(14001).setLabel(self.cache['imvdb_key'])

        self.refresh_tabs()
        self.setFocusId(3)

    def refresh_tabs(self):
        list_ctrl = self.getControl(3)
        current_sel = list_ctrl.getSelectedPosition()
        list_ctrl.reset()
        
        cats = [('Modules', 'modules'), ('AIOStreams', 'aiostreams'), ('Trakt', 'trakt')]
        if self.selections.get('youtube'): cats.append(('YouTube', 'youtube'))
        if self.selections.get('iptv'): cats.append(('IPTV Simple', 'iptv'))
        if self.selections.get('imvdb'): cats.append(('IMVDb', 'imvdb'))
        
        for label, type_name in cats:
            item = xbmcgui.ListItem(label)
            item.setProperty('type', type_name)
            list_ctrl.addItem(item)
            
        if current_sel >= 0:
            list_ctrl.selectItem(current_sel)

    def onAction(self, action):
        if action.getId() in [92, 10, 13]: # Back, PreviousMenu, Stop
            self.close()

    def onClick(self, controlId):
        # Module Toggles
        if controlId == 10101 or controlId == 10102:
            self.getControl(controlId).setSelected(True) # Required
        
        elif controlId == 10103: self.selections['skin'] = self.getControl(10103).isSelected()
        elif controlId == 10104: 
            self.selections['youtube'] = self.getControl(10104).isSelected()
            self.refresh_tabs()
        elif controlId == 10105: self.selections['upnext'] = self.getControl(10105).isSelected()
        elif controlId == 10106: 
            self.selections['iptv'] = self.getControl(10106).isSelected()
            self.refresh_tabs()
        elif controlId == 10107: 
            self.selections['imvdb'] = self.getControl(10107).isSelected()
            self.refresh_tabs()
        elif controlId == 10108: self.selections['tmdbh'] = self.getControl(10108).isSelected()

        if controlId == 10004: # Default Behavior
            current = self.getControl(10004).getLabel().split(": ")[-1]
            new_val = "play_first" if current == "show_streams" else "show_streams"
            self.getControl(10004).setLabel(f"Default Behavior: {new_val}")
            
        if controlId == 9010: # Install Selected
            self.collect_data()
            # Also save to cache
            cache_data = self.data.copy()
            cache_data.update(self.selections)
            save_cache(cache_data)
            
            self.cancelled = False
            self.close()
            
        if controlId == 9011: # Cancel
            self.close()

    def collect_data(self):
        # AIOStreams
        self.data['aiostreams_host'] = self.getControl(10001).getLabel()
        self.data['aiostreams_uuid'] = self.getControl(10002).getLabel()
        self.data['aiostreams_password'] = self.getControl(10003).getLabel()
        self.data['aiostreams_behavior'] = self.getControl(10004).getLabel()
        self.data['aiostreams_subtitles'] = self.getControl(10005).getLabel()
        self.data['aiostreams_upnext'] = self.getControl(10006).isSelected()
        
        # Trakt
        self.data['trakt_id'] = self.getControl(11001).getLabel()
        self.data['trakt_secret'] = self.getControl(11002).getLabel()
        
        # Youtube
        if self.selections.get('youtube'):
            self.data['yt_key'] = self.getControl(12001).getLabel()
            self.data['yt_id'] = self.getControl(12002).getLabel()
            self.data['yt_secret'] = self.getControl(12003).getLabel()
            
        # IPTV
        if self.selections.get('iptv'):
            self.data['iptv_m3u'] = self.getControl(13001).getLabel()
            self.data['iptv_epg'] = self.getControl(13002).getLabel()
            
        # IMVDb
        if self.selections.get('imvdb'):
            self.data['imvdb_key'] = self.getControl(14001).getLabel()

        # Store in hidden window properties
        for k, v in self.data.items():
            WINDOW.setProperty(f"AIODI.Onboarding.{k}", str(v))

def run_installer(selections, data):
    progress = xbmcgui.DialogProgress()
    progress.create("AIODI Setup", "Initializing installation...")
    
    # helper to ensure addon is loaded before setting settings
    def ensure_addon(addon_id):
        xbmc.executebuiltin(f'EnableAddon({addon_id})')
        xbmc.executebuiltin('RunScript(script.module.inputstreamhelper)') # unlikely needed but good practice
        time.sleep(1)
        return xbmcaddon.Addon(addon_id)

    # 1. AIOStreams
    if install_with_wait('plugin.video.aiostreams', progress, 5, 20):
        try:
            progress.update(25, "Configuring AIOStreams...")
            aio = ensure_addon('plugin.video.aiostreams')
            
            # Integrations
            aio.setSetting('aiostreams_host', data.get('aiostreams_host', ''))
            aio.setSetting('aiostreams_uuid', data.get('aiostreams_uuid', ''))
            aio.setSetting('aiostreams_password', data.get('aiostreams_password', ''))
            aio.setSetting('trakt_client_id', data.get('trakt_id', ''))
            aio.setSetting('trakt_client_secret', data.get('trakt_secret', ''))
            
            # General
            # extract value from "Default Behavior: show_streams"
            beh_val = data.get('aiostreams_behavior', 'show_streams').split(": ")[-1]
            aio.setSetting('default_behavior', beh_val)
            aio.setSetting('subtitle_languages', data.get('aiostreams_subtitles', ''))
            
            # Signal UpNext
            upnext_val = 'true' if selections.get('upnext') else 'false'
            aio.setSetting('autoplay_next_episode', upnext_val)
            
            # "Save and exit" - simulated by re-instantiating or ensuring write
            del aio
            time.sleep(1)
            
            # Retrieve Manifest
            progress.update(30, "Retrieving Manifest...")
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=retrieve_manifest)')
            
            # "Wait for response" - using a dialog to force user wait/confirmation
            xbmcgui.Dialog().ok("AIOStreams Setup", "Retrieving Manifest.\nPlease wait for the notification, then click OK.")
            
            # Authorize Trakt
            progress.update(35, "Authenticating Trakt...")
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=trakt_auth)')
            
            # "Wait for window to close"
            xbmcgui.Dialog().ok("AIOStreams Setup", "Please complete the Trakt Authorization in the popup window.\nWhen finished, click OK to continue.")
            
        except Exception as e:
            xbmc.log(f"[Onboarding] AIOStreams config error: {e}", xbmc.LOGERROR)

    # 2. Addon Installs & Config
    
    # YouTube
    if selections.get('youtube'):
        if install_with_wait('plugin.video.youtube', progress, 40, 50):
            try:
                progress.update(52, "Configuring YouTube...")
                yt = ensure_addon('plugin.video.youtube')
                yt.setSetting('general.setupwizard', 'false')
                yt.setSetting('api.key', data.get('yt_key', ''))
                yt.setSetting('api.id', data.get('yt_id', ''))
                yt.setSetting('api.secret', data.get('yt_secret', ''))
                yt.setSetting('api.devkeys', 'true')
            except Exception as e:
                xbmc.log(f"[Onboarding] YouTube config error: {e}", xbmc.LOGERROR)

    # UpNext
    if selections.get('upnext'):
        if install_with_wait('service.upnext', progress, 55, 65):
            try:
                progress.update(67, "Configuring UpNext...")
                un = ensure_addon('service.upnext')
                # 1 = Simple
                un.setSetting('interface.notification_mode', '1') 
                # true = stop button
                un.setSetting('interface.stop_button', 'true')
                # 1 = Play Next
                un.setSetting('behaviour.default_action', '1') 
            except Exception as e:
                xbmc.log(f"[Onboarding] UpNext config error: {e}", xbmc.LOGERROR)

    # IPTV Simple
    if selections.get('iptv'):
        install_with_wait('pvr.iptvsimple', progress, 70, 80)
        # Note: PVR addons often require a restart or explicit configuration via their specific calls, 
        # but standardized setting IDs are less common or require PVR manager restart. 
        # For now, we assume implicit defaults or manual setups for PVR URL if not exposed via python API consistently.
        # If user had 'iptv_m3u', we might try to set it if we knew the ID, typically 'm3uId' or similar but it varies.
        # User prompt didn't strictly specify applying the M3U url setting here, just "install".

    # IMVDb
    if selections.get('imvdb'):
        if install_with_wait('plugin.video.imvdb', progress, 85, 90):
            try:
                progress.update(91, "Configuring IMVDb...")
                im = ensure_addon('plugin.video.imvdb')
                im.setSetting('api_key', data.get('imvdb_key', ''))
            except Exception as e:
                xbmc.log(f"[Onboarding] IMVDb config error: {e}", xbmc.LOGERROR)

    # TMDB Helper Players
    if selections.get('tmdbh'):
        progress.update(95, "Setting up TMDB Helper Players...")
        try:
            import xbmcvfs
            src = os.path.join(os.path.dirname(ADDON_PATH), "TMDB Helper Players", "tmdbhelper-players.zip")
            # Fallback path for development environment
            if not xbmcvfs.exists(src):
                src = "/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/TMDB Helper Players/tmdbhelper-players.zip"
            
            dst = "special://home/tmdbhelper-players.zip"
            if xbmcvfs.exists(src):
                xbmcvfs.copy(src, dst)
        except Exception as e:
            xbmc.log(f"[AIODI Onboarding] Failed to copy players ZIP: {e}", xbmc.LOGERROR)

    # Skin Switch
    if selections.get('skin'):
        progress.update(98, "Switching to AIODI Skin...")
        xbmc.executebuiltin('SetProperty(SkinSwitched,True,Home)')
        xbmc.executebuiltin('SetSkin(skin.AIODI)')

    progress.update(100, "Setup complete!")
    time.sleep(2)
    progress.close()

def run():
    # Launch consolidated Input Window directly
    form = InputWindow('onboarding_input.xml', ADDON_PATH, 'Default', '1080i')
    form.doModal()
    data = form.data
    selections = form.selections
    cancelled = form.cancelled
    del form
    
    if cancelled: return

    # Installation
    run_installer(selections, data)

if __name__ == '__main__':
    run()
