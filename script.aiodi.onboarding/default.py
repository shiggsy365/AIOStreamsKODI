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

def install_with_wait(addon_id, progress, start_pct, end_pct, update_if_exists=False):
    # Check if already installed
    if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
        # Ensure addon is enabled (auto-approve if disabled)
        xbmc.log(f'[Onboarding] Ensuring {addon_id} is enabled...', xbmc.LOGINFO)
        xbmc.executebuiltin(f'EnableAddon({addon_id})')
        time.sleep(0.5)

        if update_if_exists:
            try:
                # Get current version
                current_addon = xbmcaddon.Addon(addon_id)
                current_version = current_addon.getAddonInfo('version')
                xbmc.log(f'[Onboarding] {addon_id} already installed (v{current_version}), checking for updates...', xbmc.LOGINFO)
                progress.update(int(start_pct), f"Updating {addon_id}...")

                # Trigger update check
                xbmc.executebuiltin(f'UpdateAddon({addon_id})')

                # Wait for potential update (max 30s)
                for i in range(60):
                    if progress.iscanceled(): return False
                    time.sleep(0.5)
                    try:
                        updated_addon = xbmcaddon.Addon(addon_id)
                        new_version = updated_addon.getAddonInfo('version')
                        if new_version != current_version:
                            xbmc.log(f'[Onboarding] {addon_id} updated from v{current_version} to v{new_version}', xbmc.LOGINFO)
                            progress.update(int(end_pct), f"{addon_id} updated to v{new_version}")
                            time.sleep(0.5)
                            return True
                    except:
                        pass

                # No update found or same version
                xbmc.log(f'[Onboarding] {addon_id} already at latest version (v{current_version})', xbmc.LOGINFO)
                progress.update(int(end_pct), f"{addon_id} already up to date")
                time.sleep(0.5)
                return True
            except Exception as e:
                xbmc.log(f'[Onboarding] Error checking version for {addon_id}: {e}', xbmc.LOGERROR)
                progress.update(int(end_pct), f"{addon_id} already installed")
                return True
        else:
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
            # Auto-enable after installation to approve any dependency prompts
            xbmc.log(f'[Onboarding] {addon_id} installed, ensuring it is enabled...', xbmc.LOGINFO)
            xbmc.executebuiltin(f'EnableAddon({addon_id})')
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

        # Let Kodi handle navigation normally - don't intercept

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

    # 1. Install AIOStreams Plugin (or update if already installed)
    if install_with_wait('plugin.video.aiostreams', progress, 5, 20, update_if_exists=True):
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
            # Wait for manifest retrieval to complete (silent)
            time.sleep(8)

            # Call integrations/authorize trakt (silent, user can do this later if needed)
            progress.update(35, "Configuring Trakt...")
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=trakt_auth)')
            # Give it time to process in background
            time.sleep(3)

            # Save and exit aiostreams settings again
            aio = ensure_addon('plugin.video.aiostreams')
            if aio:
                del aio
                time.sleep(1)

        except Exception as e:
            xbmc.log(f"[Onboarding] AIOStreams config error: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Setup Error", f"AIOStreams configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 2. If requested, Install YouTube plugin from kodi repository (or update if already installed)
    if selections.get('youtube'):
        if install_with_wait('plugin.video.youtube', progress, 40, 50, update_if_exists=True):
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

    # 3. If requested, Install Up Next plugin from kodi repository (or update if already installed)
    if selections.get('upnext'):
        if install_with_wait('service.upnext', progress, 55, 65, update_if_exists=True):
            try:
                progress.update(67, "Configuring UpNext...")
                un = ensure_addon('service.upnext')
                if un:
                    # Change interface/set display mode for notifications to Simple
                    un.setSetting('simpleMode', '1')  # 1 = Simple, 0 = Fancy
                    # Enable interface/show a stop button instead of a close button
                    un.setSetting('stopAfterClose', 'true')
                    # Change behaviour/default action when nothing selected to 'Play Next'
                    un.setSetting('autoPlayMode', '0')  # 0 = Auto play next episode
                    del un
            except Exception as e:
                xbmc.log(f"[Onboarding] UpNext config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"UpNext configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 4. If requested install IPTV Simple Player from kodi repository (or update if already installed)
    if selections.get('iptv'):
        if install_with_wait('pvr.iptvsimple', progress, 70, 78, update_if_exists=True):
            try:
                progress.update(79, "Configuring IPTV Simple Player...")
                iptv = ensure_addon('pvr.iptvsimple')
                if iptv:
                    # Configure M3U URL if provided
                    m3u_url = data.get('iptv_m3u', '')
                    if m3u_url:
                        iptv.setSetting('m3uPathType', '1')  # 1 = Remote path (URL)
                        iptv.setSetting('m3uUrl', m3u_url)

                    # Configure EPG URL if provided
                    epg_url = data.get('iptv_epg', '')
                    if epg_url:
                        iptv.setSetting('epgPathType', '1')  # 1 = Remote path (URL)
                        iptv.setSetting('epgUrl', epg_url)

                    del iptv
                    xbmc.log('[Onboarding] IPTV Simple Player configured successfully', xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"[Onboarding] IPTV config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"IPTV configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 5. If requested install IMVDb plugin from my repository (or update if already installed)
    if selections.get('imvdb'):
        if install_with_wait('plugin.video.imvdb', progress, 85, 90, update_if_exists=True):
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
    # Configuration is already done, user can sign in later through the YouTube addon if needed
    if selections.get('youtube') and xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)'):
        xbmc.log('[Onboarding] YouTube configured, user can sign in later through addon', xbmc.LOGINFO)

    # 8. If requested install AIODI skin, and switch to it
    xbmc.log(f'[Onboarding] Checking skin installation - selections.get("skin"): {selections.get("skin")}', xbmc.LOGINFO)
    if selections.get('skin'):
        xbmc.log('[Onboarding] Skin installation requested', xbmc.LOGINFO)
        # Install or update the skin (don't reinstall if already present)
        if install_with_wait('skin.AIODI', progress, 96, 98, update_if_exists=True):
            xbmc.log('[Onboarding] Skin ready, switching...', xbmc.LOGINFO)
            progress.update(99, "Switching to AIODI Skin...")
            xbmc.executebuiltin('Skin.SetString(first_run,done)')  # Mark first run as complete
            time.sleep(2)
            xbmc.executebuiltin('SetSkin(skin.AIODI)')
            xbmc.log('[Onboarding] SetSkin command issued', xbmc.LOGINFO)
        else:
            xbmc.log('[Onboarding] Skin installation failed or timed out', xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Setup Warning", "AIODI skin installation failed", xbmcgui.NOTIFICATION_WARNING)
    else:
        xbmc.log('[Onboarding] Skin installation not requested (selections.get("skin") returned False/None)', xbmc.LOGINFO)

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
