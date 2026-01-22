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
    # Check if already installed - if so, skip installation
    if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
        xbmc.log(f'[Onboarding] {addon_id} already installed, skipping...', xbmc.LOGINFO)
        progress.update(int(end_pct), f"{addon_id} already installed")
        time.sleep(0.5)
        return True

    progress.update(int(start_pct), f"Installing {addon_id}...")
    xbmc.executebuiltin(f'InstallAddon({addon_id})')

    # Wait loop (max 60s)
    for i in range(120):
        if progress.iscanceled(): return False
        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            progress.update(int(end_pct), f"{addon_id} installed successfully")
            time.sleep(0.5)
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
        try:
            # Initial radio button states for Modules tab
            self.getControl(10101).setSelected(True) # AIOStreams
            self.getControl(10102).setSelected(True) # Trakt
            self.getControl(10103).setSelected(self.selections['skin'])
            self.getControl(10104).setSelected(self.selections['youtube'])
            self.getControl(10105).setSelected(self.selections['upnext'])
            self.getControl(10106).setSelected(self.selections['iptv'])
            self.getControl(10107).setSelected(self.selections['imvdb'])
            self.getControl(10108).setSelected(self.selections['tmdbh'])

            # Pre-fill settings from cache - use setText() for edit controls
            if 'aiostreams_host' in self.cache:
                self.getControl(10001).setText(self.cache['aiostreams_host'])
            if 'aiostreams_uuid' in self.cache:
                self.getControl(10002).setText(self.cache['aiostreams_uuid'])
            if 'aiostreams_password' in self.cache:
                self.getControl(10003).setText(self.cache['aiostreams_password'])
            if 'aiostreams_behavior' in self.cache:
                # Restore button label with proper format
                self.getControl(10004).setLabel(f"Default Behavior: {self.cache['aiostreams_behavior']}")
            if 'aiostreams_subtitles' in self.cache:
                self.getControl(10005).setText(self.cache['aiostreams_subtitles'])
            if 'aiostreams_upnext' in self.cache:
                self.getControl(10006).setSelected(self.cache['aiostreams_upnext'])

            if 'trakt_id' in self.cache:
                self.getControl(11001).setText(self.cache['trakt_id'])
            if 'trakt_secret' in self.cache:
                self.getControl(11002).setText(self.cache['trakt_secret'])

            if 'yt_key' in self.cache:
                self.getControl(12001).setText(self.cache['yt_key'])
            if 'yt_id' in self.cache:
                self.getControl(12002).setText(self.cache['yt_id'])
            if 'yt_secret' in self.cache:
                self.getControl(12003).setText(self.cache['yt_secret'])

            if 'iptv_m3u' in self.cache:
                self.getControl(13001).setText(self.cache['iptv_m3u'])
            if 'iptv_epg' in self.cache:
                self.getControl(13002).setText(self.cache['iptv_epg'])

            if 'imvdb_key' in self.cache:
                self.getControl(14001).setText(self.cache['imvdb_key'])

            self.refresh_tabs()
            self.setFocusId(3)
        except Exception as e:
            xbmc.log(f'[Onboarding] Error in onInit: {e}', xbmc.LOGERROR)

    def refresh_tabs(self):
        try:
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

            # Ensure we select a valid item
            if current_sel >= 0 and current_sel < len(cats):
                list_ctrl.selectItem(current_sel)
            else:
                list_ctrl.selectItem(0)
        except Exception as e:
            xbmc.log(f'[Onboarding] Error refreshing tabs: {e}', xbmc.LOGERROR)

    def onAction(self, action):
        action_id = action.getId()

        # Handle back/cancel actions
        if action_id in [92, 10, 13]: # Back, PreviousMenu, Stop
            self.close()
            return

        # Prevent navigation crashes by catching invalid navigation attempts
        try:
            focused_control = self.getFocusId()

            # If trying to navigate in grouplist (ID 5), ensure safe navigation
            if focused_control in range(10000, 15000):
                # Up/Down in grouplist - let Kodi handle it normally
                if action_id in [3, 4]: # Up, Down
                    pass  # Let default behavior handle scrolling
                # Left/Right - navigate to category list or buttons
                elif action_id == 1: # Left
                    self.setFocusId(3)
                elif action_id == 2: # Right
                    self.setFocusId(9500)
        except Exception as e:
            xbmc.log(f'[Onboarding] Navigation error: {e}', xbmc.LOGERROR)
            # On error, return focus to a safe control
            try:
                self.setFocusId(3)
            except:
                pass

    def onClick(self, controlId):
        try:
            # Module Toggles
            if controlId == 10101 or controlId == 10102:
                self.getControl(controlId).setSelected(True) # Required

            elif controlId == 10103:
                self.selections['skin'] = self.getControl(10103).isSelected()
            elif controlId == 10104:
                self.selections['youtube'] = self.getControl(10104).isSelected()
                self.refresh_tabs()
            elif controlId == 10105:
                self.selections['upnext'] = self.getControl(10105).isSelected()
            elif controlId == 10106:
                self.selections['iptv'] = self.getControl(10106).isSelected()
                self.refresh_tabs()
            elif controlId == 10107:
                self.selections['imvdb'] = self.getControl(10107).isSelected()
                self.refresh_tabs()
            elif controlId == 10108:
                self.selections['tmdbh'] = self.getControl(10108).isSelected()

            if controlId == 10004: # Default Behavior toggle
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
        except Exception as e:
            xbmc.log(f'[Onboarding] Error in onClick for control {controlId}: {e}', xbmc.LOGERROR)

    def collect_data(self):
        try:
            # AIOStreams - use getText() for edit controls
            self.data['aiostreams_host'] = self.getControl(10001).getText()
            self.data['aiostreams_uuid'] = self.getControl(10002).getText()
            self.data['aiostreams_password'] = self.getControl(10003).getText()
            # Extract just the behavior value (remove "Default Behavior: " prefix)
            behavior_label = self.getControl(10004).getLabel()
            self.data['aiostreams_behavior'] = behavior_label.split(": ")[-1] if ": " in behavior_label else behavior_label
            self.data['aiostreams_subtitles'] = self.getControl(10005).getText()
            self.data['aiostreams_upnext'] = self.getControl(10006).isSelected()

            # Trakt
            self.data['trakt_id'] = self.getControl(11001).getText()
            self.data['trakt_secret'] = self.getControl(11002).getText()

            # Youtube
            if self.selections.get('youtube'):
                self.data['yt_key'] = self.getControl(12001).getText()
                self.data['yt_id'] = self.getControl(12002).getText()
                self.data['yt_secret'] = self.getControl(12003).getText()

            # IPTV
            if self.selections.get('iptv'):
                self.data['iptv_m3u'] = self.getControl(13001).getText()
                self.data['iptv_epg'] = self.getControl(13002).getText()

            # IMVDb
            if self.selections.get('imvdb'):
                self.data['imvdb_key'] = self.getControl(14001).getText()

            # Store in hidden window properties
            for k, v in self.data.items():
                WINDOW.setProperty(f"AIODI.Onboarding.{k}", str(v))
        except Exception as e:
            xbmc.log(f'[Onboarding] Error collecting data: {e}', xbmc.LOGERROR)

def run_installer(selections, data):
    progress = xbmcgui.DialogProgress()
    progress.create("AIODI Setup", "Initializing installation...")

    # helper to ensure addon is loaded before setting settings
    def ensure_addon(addon_id):
        xbmc.executebuiltin(f'EnableAddon({addon_id})')
        time.sleep(2)  # Give addon time to load
        try:
            return xbmcaddon.Addon(addon_id)
        except Exception as e:
            xbmc.log(f"[Onboarding] Failed to load addon {addon_id}: {e}", xbmc.LOGERROR)
            return None

    # 1. Install AIOStreams Plugin
    if install_with_wait('plugin.video.aiostreams', progress, 5, 20):
        try:
            progress.update(25, "Configuring AIOStreams...")
            aio = ensure_addon('plugin.video.aiostreams')
            if not aio:
                raise Exception("Failed to load AIOStreams addon")

            # Add integrations/host base url to settings
            aio.setSetting('aiostreams_host', data.get('aiostreams_host', ''))
            # Add integrations/uuid to settings
            aio.setSetting('aiostreams_uuid', data.get('aiostreams_uuid', ''))
            # Add integrations/password to settings
            aio.setSetting('aiostreams_password', data.get('aiostreams_password', ''))
            # Add integrations/trakt client id to settings
            aio.setSetting('trakt_client_id', data.get('trakt_id', ''))
            # Add integrations/trakt client secret to settings
            aio.setSetting('trakt_client_secret', data.get('trakt_secret', ''))

            # Set general/default behaviour to either play_first or show_streams
            behavior_val = data.get('aiostreams_behavior', 'show_streams')
            aio.setSetting('default_behavior', behavior_val)

            # Add filter subtitles to general/filter subtitles
            aio.setSetting('subtitle_languages', data.get('aiostreams_subtitles', ''))

            # If UpNext is toggled to be installed, turn on general/Signal UpNext
            upnext_val = 'true' if selections.get('upnext') else 'false'
            aio.setSetting('autoplay_next_episode', upnext_val)

            # Save and exit aiostreams settings
            del aio
            time.sleep(2)

            # Return to aiostreams settings and call integrations/retrieve manifest
            progress.update(30, "Retrieving Manifest...")
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=retrieve_manifest)')
            # Wait for a response
            time.sleep(3)
            xbmcgui.Dialog().ok("AIOStreams Setup", "Retrieving Manifest.\nPlease wait for the notification, then click OK.")

            # Call integrations/authorize trakt, wait for window to close
            progress.update(35, "Authenticating Trakt...")
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=trakt_auth)')
            # Wait for window to close
            xbmcgui.Dialog().ok("AIOStreams Setup", "Please complete the Trakt Authorization in the popup window.\nWhen finished, click OK to continue.")

            # Save and exit aiostreams settings again
            aio = ensure_addon('plugin.video.aiostreams')
            if aio:
                del aio
                time.sleep(1)

        except Exception as e:
            xbmc.log(f"[Onboarding] AIOStreams config error: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Setup Error", f"AIOStreams configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 2. If requested, Install YouTube plugin from kodi repository
    if selections.get('youtube'):
        if install_with_wait('plugin.video.youtube', progress, 40, 50):
            try:
                progress.update(52, "Configuring YouTube...")
                yt = ensure_addon('plugin.video.youtube')
                if yt:
                    # Turn off general/enable setup wizard
                    yt.setSetting('youtube.folder.my_subscriptions.show', 'false')
                    # Enter API Key in API/API Key
                    yt.setSetting('youtube.api.key', data.get('yt_key', ''))
                    # Enter API ID in API/API ID
                    yt.setSetting('youtube.api.id', data.get('yt_id', ''))
                    # Enter API Secret in API/API Secret
                    yt.setSetting('youtube.api.secret', data.get('yt_secret', ''))
                    # Turn on API/allow developer keys
                    yt.setSetting('youtube.api.enable', 'true')
                    del yt
            except Exception as e:
                xbmc.log(f"[Onboarding] YouTube config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"YouTube configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 3. If requested, Install Up Next plugin from kodi repository
    if selections.get('upnext'):
        if install_with_wait('service.upnext', progress, 55, 65):
            try:
                progress.update(67, "Configuring UpNext...")
                un = ensure_addon('service.upnext')
                if un:
                    # Change interface/set display mode for notifications to Simple
                    un.setSetting('simpleMode', '0')  # 0 = Simple, 1 = Fancy
                    # Enable interface/show a stop button instead of a close button
                    un.setSetting('stopAfterClose', 'true')
                    # Change behaviour/default action when nothing selected to 'Play Next'
                    un.setSetting('autoPlayMode', '0')  # 0 = Auto play next episode
                    del un
            except Exception as e:
                xbmc.log(f"[Onboarding] UpNext config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"UpNext configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 4. If requested install IPTV Simple Player from kodi repository
    if selections.get('iptv'):
        install_with_wait('pvr.iptvsimple', progress, 70, 80)

    # 5. If requested install IMVDb plugin from my repository
    if selections.get('imvdb'):
        if install_with_wait('plugin.video.imvdb', progress, 85, 90):
            try:
                progress.update(91, "Configuring IMVDb...")
                im = ensure_addon('plugin.video.imvdb')
                if im:
                    # In settings, set IMVDb API Key
                    im.setSetting('api_key', data.get('imvdb_key', ''))
                    del im
            except Exception as e:
                xbmc.log(f"[Onboarding] IMVDb config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"IMVDb configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 6. If TMDB helper players are selected, save a copy of the zip file to the special://home directory
    if selections.get('tmdbh'):
        progress.update(95, "Setting up TMDB Helper Players...")
        try:
            src = os.path.join(os.path.dirname(ADDON_PATH), "TMDB Helper Players", "tmdbhelper-players.zip")
            # Fallback path for development environment
            if not xbmcvfs.exists(src):
                src = "/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/TMDB Helper Players/tmdbhelper-players.zip"

            dst = xbmcvfs.translatePath("special://home/tmdbhelper-players.zip")
            if xbmcvfs.exists(src):
                xbmcvfs.copy(src, dst)
                xbmc.log(f"[Onboarding] TMDB Helper Players copied to {dst}", xbmc.LOGINFO)
            else:
                xbmc.log(f"[Onboarding] TMDB Helper Players source not found at {src}", xbmc.LOGWARNING)
        except Exception as e:
            xbmc.log(f"[Onboarding] Failed to copy players ZIP: {e}", xbmc.LOGERROR)

    # 7. YouTube interactive setup (if YouTube was installed)
    if selections.get('youtube') and xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)'):
        # Check if user is already signed in by checking for access token
        try:
            yt_check = ensure_addon('plugin.video.youtube')
            is_signed_in = False
            if yt_check:
                # Check if access token exists (indicates user is signed in)
                access_token = yt_check.getSetting('youtube.access.token')
                if access_token and access_token.strip():
                    is_signed_in = True
                    xbmc.log('[Onboarding] YouTube already signed in, skipping interactive setup', xbmc.LOGINFO)
                del yt_check
        except Exception as e:
            xbmc.log(f'[Onboarding] Error checking YouTube sign-in status: {e}', xbmc.LOGERROR)
            is_signed_in = False

        # Only show interactive setup if not already signed in
        if not is_signed_in:
            progress.close()
            # Prompt user to complete YouTube setup
            xbmcgui.Dialog().ok(
                "YouTube Setup Required",
                "Please complete the YouTube setup wizard that will now open.\n"
                "After completing the wizard, select the first option and choose 'Sign In'.\n"
                "Once all dialogs have closed, the setup will continue."
            )

            # Open YouTube addon settings
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.youtube)')

            # Wait for user to complete setup
            xbmcgui.Dialog().ok(
                "YouTube Setup",
                "When you have finished signing in to YouTube and all dialogs have closed,\n"
                "click OK to continue with the AIODI skin installation."
            )

            # Recreate progress dialog for remaining steps
            progress = xbmcgui.DialogProgress()
            progress.create("AIODI Setup", "Continuing installation...")

    # 8. If requested install AIODI skin, and switch to it
    if selections.get('skin'):
        progress.update(98, "Switching to AIODI Skin...")
        xbmc.executebuiltin('SetProperty(SkinSwitched,True,Home)')
        xbmc.executebuiltin('Skin.SetString(first_run,done)')  # Mark first run as complete
        time.sleep(1)
        xbmc.executebuiltin('ActivateWindow(yesnodialog)')
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
