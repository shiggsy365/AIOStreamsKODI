import xbmc
import xbmcgui
import xbmcaddon
import os
import json
import threading
import time

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
WINDOW = xbmcgui.Window(10000) # Home window for property storage

# Selection IDs from onboarding.xml
ID_AIOSTREAMS = 1101
ID_TRAKT = 1102
ID_SKIN = 2101
ID_YOUTUBE = 2102
ID_UPNEXT = 2103
ID_IPTV = 3101
ID_IMVDB = 3102
ID_TMDBH = 3103

class OnboardingWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super(OnboardingWindow, self).__init__(*args, **kwargs)
        self.selections = {}

    def onInit(self):
        # Mandatory selections
        self.getControl(ID_AIOSTREAMS).setSelected(True)
        self.getControl(ID_TRAKT).setSelected(True)

    def onClick(self, controlId):
        if controlId in [ID_AIOSTREAMS, ID_TRAKT]:
            # Don't let user toggle them off
            self.getControl(controlId).setSelected(True)
        
        if controlId == 9000: # Install Selected
            self.selections = {
                'aiostreams': True,
                'trakt': True,
                'skin': self.getControl(ID_SKIN).isSelected(),
                'youtube': self.getControl(ID_YOUTUBE).isSelected(),
                'upnext': self.getControl(ID_UPNEXT).isSelected(),
                'iptv': self.getControl(ID_IPTV).isSelected(),
                'imvdb': self.getControl(ID_IMVDB).isSelected(),
                'tmdbh': self.getControl(ID_TMDBH).isSelected()
            }
            self.close()

class InputWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super(InputWindow, self).__init__(*args, **kwargs)
        # Initialize selections with defaults
        self.selections = {
            'aiostreams': True,
            'trakt': True,
            'skin': True,
            'youtube': False,
            'upnext': True,
            'iptv': False,
            'imvdb': False,
            'tmdbh': True
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
    
    # 1. AIOStreams
    progress.update(10, "Configuring AIOStreams...")
    aio = xbmcaddon.Addon('plugin.video.aiostreams')
    aio.setSetting('aiostreams_host', data.get('aiostreams_host', ''))
    aio.setSetting('aiostreams_uuid', data.get('aiostreams_uuid', ''))
    aio.setSetting('aiostreams_password', data.get('aiostreams_password', ''))
    aio.setSetting('trakt_client_id', data.get('trakt_id', ''))
    aio.setSetting('trakt_client_secret', data.get('trakt_secret', ''))
    aio.setSetting('default_behavior', data.get('aiostreams_behavior', 'show_streams'))
    aio.setSetting('subtitle_languages', data.get('aiostreams_subtitles', ''))
    aio.setSetting('autoplay_next_episode', 'true' if data.get('aiostreams_upnext') else 'false')
    
    # Trigger manifest & trakt auth
    progress.update(30, "Retrieving manifest and authenticating Trakt...")
    xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=retrieve_manifest)')
    # Wait a bit for manifest
    time.sleep(2)
    xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=trakt_auth)')

    # 2. Addon Installs
    def install_builtin(addon_id):
        xbmc.executebuiltin(f'InstallAddon({addon_id})')

    if selections.get('youtube'):
        progress.update(50, "Installing YouTube...")
        install_builtin('plugin.video.youtube')
        time.sleep(2)
        try:
            yt = xbmcaddon.Addon('plugin.video.youtube')
            yt.setSetting('general.setupwizard', 'false')
            yt.setSetting('api.key', data.get('yt_key', ''))
            yt.setSetting('api.id', data.get('yt_id', ''))
            yt.setSetting('api.secret', data.get('yt_secret', ''))
            yt.setSetting('api.devkeys', 'true')
        except: pass

    if selections.get('upnext'):
        progress.update(60, "Installing UpNext...")
        install_builtin('service.upnext')
        time.sleep(2)
        try:
            un = xbmcaddon.Addon('service.upnext')
            un.setSetting('interface.notification_mode', '1') # Simple
            un.setSetting('interface.stop_button', 'true')
            un.setSetting('behaviour.default_action', '1') # Play Next
        except: pass

    if selections.get('iptv'):
        progress.update(70, "Installing IPTV Simple...")
        install_builtin('pvr.iptvsimple')

    if selections.get('imvdb'):
        progress.update(80, "Installing IMVDb...")
        install_builtin('plugin.video.imvdb')
        time.sleep(1)
        try:
            im = xbmcaddon.Addon('plugin.video.imvdb')
            im.setSetting('api_key', data.get('imvdb_key', ''))
        except: pass

    if selections.get('tmdbh'):
        progress.update(90, "Setting up TMDB Helper Players...")
        try:
            import xbmcvfs
            src = os.path.join(os.path.dirname(ADDON_PATH), "TMDB Helper Players", "tmdbhelper-players.zip")
            if not xbmcvfs.exists(src):
                src = "/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/TMDB Helper Players/tmdbhelper-players.zip"
            
            dst = "special://home/tmdbhelper-players.zip"
            xbmcvfs.copy(src, dst)
        except Exception as e:
            xbmc.log(f"[AIODI Onboarding] Failed to copy players ZIP: {e}", xbmc.LOGERROR)

    if selections.get('skin'):
        progress.update(95, "Switching to AIODI Skin...")
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


if __name__ == '__main__':
    run()
