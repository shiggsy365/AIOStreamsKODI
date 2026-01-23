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

def install_with_wait(addon_id, progress, start_pct, end_pct, update_if_exists=False, silent=False, max_wait_time=60):
    # Check if already installed
    if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
        # Ensure addon is enabled (auto-approve if disabled)
        if not silent:
            xbmc.log(f'[Onboarding] Ensuring {addon_id} is enabled...', xbmc.LOGINFO)
        xbmc.executebuiltin(f'EnableAddon({addon_id})')
        time.sleep(0.1)  # Reduced for faster notification clearing

        if update_if_exists:
            try:
                # Get current version
                current_addon = xbmcaddon.Addon(addon_id)
                current_version = current_addon.getAddonInfo('version')
                xbmc.log(f'[Onboarding] {addon_id} already installed (v{current_version}), checking for updates...', xbmc.LOGINFO)
                progress.update(int(start_pct), f"Updating {addon_id}...")

                # Trigger update check
                xbmc.executebuiltin(f'UpdateAddon({addon_id})')

                # Auto-approve update dialog and clear notification quickly
                time.sleep(0.3)  # Brief wait for dialog to appear
                xbmc.executebuiltin('SendClick(12)')  # Click Yes on dialog
                time.sleep(0.1)  # Minimal wait to clear notification

                # Wait for potential update (max 30s) with progress updates
                for i in range(60):
                    if progress.iscanceled(): return False

                    # Update progress every 5 iterations to keep dialog visible
                    if i % 5 == 0:
                        elapsed = i * 0.5
                        pct = int(start_pct + ((i / 60) * (end_pct - start_pct)))
                        progress.update(pct, f"Updating {addon_id}... ({int(elapsed)}s)")

                    time.sleep(0.5)
                    try:
                        updated_addon = xbmcaddon.Addon(addon_id)
                        new_version = updated_addon.getAddonInfo('version')
                        if new_version != current_version:
                            xbmc.log(f'[Onboarding] {addon_id} updated from v{current_version} to v{new_version}', xbmc.LOGINFO)
                            progress.update(int(end_pct), f"{addon_id} updated to v{new_version}")
                            time.sleep(0.1)  # Reduced for faster notification clearing
                            return True
                    except:
                        pass

                # No update found or same version
                xbmc.log(f'[Onboarding] {addon_id} already at latest version (v{current_version})', xbmc.LOGINFO)
                progress.update(int(end_pct), f"{addon_id} already up to date")
                time.sleep(0.1)  # Reduced for faster notification clearing
                return True
            except Exception as e:
                xbmc.log(f'[Onboarding] Error checking version for {addon_id}: {e}', xbmc.LOGERROR)
                progress.update(int(end_pct), f"{addon_id} already installed")
                return True
        else:
            xbmc.log(f'[Onboarding] {addon_id} already installed, skipping...', xbmc.LOGINFO)
            progress.update(int(end_pct), f"{addon_id} already installed")
            time.sleep(0.1)  # Reduced for faster notification clearing
            return True

    progress.update(int(start_pct), f"Installing {addon_id}...")
    xbmc.executebuiltin(f'InstallAddon({addon_id})')

    # Auto-approve installation dialog and clear notification quickly
    time.sleep(0.3)  # Brief wait for dialog to appear
    xbmc.executebuiltin('SendClick(12)')  # Click Yes on dialog
    time.sleep(0.1)  # Minimal wait to clear notification

    # Wait loop with progress updates (max_wait_time seconds)
    max_iterations = int(max_wait_time / 0.5)  # 0.5s per iteration
    for i in range(max_iterations):
        if progress.iscanceled(): return False

        # Update progress every 10 iterations to keep dialog visible
        if i % 10 == 0:
            elapsed = i * 0.5
            pct = int(start_pct + ((i / max_iterations) * (end_pct - start_pct)))
            progress.update(pct, f"Installing {addon_id}... ({int(elapsed)}s)")

        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            # Auto-enable after installation to approve any dependency prompts
            xbmc.log(f'[Onboarding] {addon_id} installed, ensuring it is enabled...', xbmc.LOGINFO)
            xbmc.executebuiltin(f'EnableAddon({addon_id})')
            progress.update(int(end_pct), f"{addon_id} installed successfully")
            time.sleep(0.1)  # Reduced for faster notification clearing
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

def pre_install_dependencies(progress, selections):
    """Pre-install all dependencies to suppress popup dialogs during main installation"""
    # Core dependencies needed by multiple addons
    core_deps = [
        'inputstream.adaptive',     # Common streaming dependency
        'script.module.requests',    # HTTP library
        'script.module.routing',     # Routing library
        'script.module.kodi-six',    # Python 2/3 compatibility
        'script.module.simplecache', # Caching library
        'script.module.urllib3',     # HTTP library
        'script.module.chardet',     # Character encoding detection
        'script.module.certifi',     # SSL certificates
        'script.module.idna',        # Internationalized domain names
    ]

    # Add addon-specific dependencies based on selections
    addon_deps = []
    if selections.get('youtube'):
        addon_deps.extend([
            'script.module.six',
            'script.module.beautifulsoup4',
        ])
    if selections.get('upnext'):
        addon_deps.append('script.module.arrow')
    if selections.get('iptv'):
        addon_deps.append('script.module.dateutil')

    all_deps = list(set(core_deps + addon_deps))  # Remove duplicates
    total_deps = len(all_deps)

    xbmc.log(f'[Onboarding] Pre-installing {total_deps} dependencies...', xbmc.LOGINFO)
    progress.update(1, f"Installing dependencies (0/{total_deps})...")

    for idx, dep in enumerate(all_deps, 1):
        if not xbmc.getCondVisibility(f'System.HasAddon({dep})'):
            xbmc.log(f'[Onboarding] Installing dependency {idx}/{total_deps}: {dep}', xbmc.LOGINFO)
            base_pct = 1 + int((idx / total_deps) * 4)
            progress.update(base_pct, f"Installing dependencies ({idx}/{total_deps}): {dep.split('.')[-1]}...")
            xbmc.executebuiltin(f'InstallAddon({dep})')

            # Auto-approve installation dialog and clear notification quickly
            time.sleep(0.3)  # Brief wait for dialog to appear
            xbmc.executebuiltin('SendClick(12)')  # Click Yes on dialog
            time.sleep(0.1)  # Minimal wait to clear notification

            # Wait for installation with timeout and progress updates
            for wait_iter in range(20):  # Max 10 seconds per dependency
                # Update progress every 4 iterations
                if wait_iter % 4 == 0:
                    elapsed = wait_iter * 0.5
                    progress.update(base_pct, f"Installing {dep.split('.')[-1]}... ({int(elapsed)}s)")

                if xbmc.getCondVisibility(f'System.HasAddon({dep})'):
                    xbmc.executebuiltin(f'EnableAddon({dep})')
                    time.sleep(0.1)  # Quick clear of enable notification
                    progress.update(base_pct, f"Dependency {idx}/{total_deps} ready: {dep.split('.')[-1]}")
                    break
                time.sleep(0.5)
        else:
            # Ensure it's enabled even if already installed
            xbmc.executebuiltin(f'EnableAddon({dep})')
            time.sleep(0.1)  # Quick clear
            xbmc.log(f'[Onboarding] Dependency {idx}/{total_deps} already installed: {dep}', xbmc.LOGINFO)
            progress.update(1 + int((idx / total_deps) * 4), f"Dependencies ({idx}/{total_deps}): {dep.split('.')[-1]} ready")

    progress.update(5, f"Dependencies ready ({total_deps}/{total_deps})")
    time.sleep(0.5)

def run_installer(selections, data):
    # Use notifications instead of progress dialog
    def notify(message):
        xbmcgui.Dialog().notification("AIODI Setup", message, xbmcgui.NOTIFICATION_INFO, 3000)

    notify("Starting installation...")

    # Create a dummy progress object for compatibility
    class DummyProgress:
        def update(self, pct, msg=""): notify(msg) if msg else None
        def iscanceled(self): return False
        def close(self): pass

    progress = DummyProgress()

    # Log received data for debugging
    xbmc.log(f"[Onboarding] Installer started with selections: {selections}", xbmc.LOGINFO)
    # Log non-sensitive data only
    data_keys = list(data.keys())
    xbmc.log(f"[Onboarding] Received data keys: {data_keys}", xbmc.LOGINFO)

    # Pre-install all dependencies to prevent popup dialogs
    pre_install_dependencies(progress, selections)

    # helper to ensure addon is loaded before setting settings
    def ensure_addon(addon_id, max_attempts=5):
        """Ensure addon is enabled and loadable, with retry logic"""
        xbmc.executebuiltin(f'EnableAddon({addon_id})')

        # Try multiple times with increasing delays
        for attempt in range(max_attempts):
            time.sleep(0.5 + (attempt * 0.3))  # Increasing delay: 0.5s, 0.8s, 1.1s, etc.
            try:
                addon = xbmcaddon.Addon(addon_id)
                xbmc.log(f"[Onboarding] Successfully loaded addon {addon_id} on attempt {attempt + 1}", xbmc.LOGINFO)
                return addon
            except Exception as e:
                if attempt < max_attempts - 1:
                    xbmc.log(f"[Onboarding] Attempt {attempt + 1} to load addon {addon_id} failed, retrying: {e}", xbmc.LOGWARNING)
                else:
                    xbmc.log(f"[Onboarding] Failed to load addon {addon_id} after {max_attempts} attempts: {e}", xbmc.LOGERROR)
        return None

    # Helper to apply settings with logging
    def apply_setting(addon, key, value, description=""):
        """Apply a setting and log the action"""
        try:
            # Convert boolean values to strings
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            addon.setSetting(key, str(value))
            # Log without exposing sensitive values
            if 'password' in key.lower() or 'secret' in key.lower() or 'key' in key.lower():
                xbmc.log(f"[Onboarding] Set {description or key}: [REDACTED]", xbmc.LOGINFO)
            else:
                xbmc.log(f"[Onboarding] Set {description or key}: {value}", xbmc.LOGINFO)
            return True
        except Exception as e:
            xbmc.log(f"[Onboarding] Failed to set {description or key}: {e}", xbmc.LOGERROR)
            return False

    # Calculate total steps for progress tracking
    total_steps = 2  # AIOStreams + Trakt (always installed)
    if selections.get('youtube'): total_steps += 1
    if selections.get('upnext'): total_steps += 1
    if selections.get('iptv'): total_steps += 1
    if selections.get('imvdb'): total_steps += 1
    if selections.get('tmdbh'): total_steps += 1
    if selections.get('skin'): total_steps += 1

    current_step = 0

    # 1. Install AIOStreams Plugin (or update if already installed)
    current_step += 1
    xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Installing AIOStreams', xbmc.LOGINFO)
    notify(f"Step {current_step}/{total_steps}: Installing AIOStreams...")
    if install_with_wait('plugin.video.aiostreams', progress, 10, 20, update_if_exists=True):
        try:
            notify(f"Step {current_step}/{total_steps}: Configuring AIOStreams...")
            aio = ensure_addon('plugin.video.aiostreams')
            if not aio:
                raise Exception("Failed to load AIOStreams addon")

            # Check if addon profile directory exists (where settings are stored)
            addon_profile = xbmcvfs.translatePath(aio.getAddonInfo('profile'))
            if not xbmcvfs.exists(addon_profile):
                xbmc.log(f"[Onboarding] Creating addon profile directory: {addon_profile}", xbmc.LOGINFO)
                xbmcvfs.mkdirs(addon_profile)

            xbmc.log("[Onboarding] Applying AIOStreams settings...", xbmc.LOGINFO)

            # Apply and verify each setting
            settings_to_apply = [
                ('aiostreams_host', data.get('aiostreams_host', ''), 'AIOStreams Host'),
                ('aiostreams_uuid', data.get('aiostreams_uuid', ''), 'AIOStreams UUID'),
                ('aiostreams_password', data.get('aiostreams_password', ''), 'AIOStreams Password'),
                ('trakt_client_id', data.get('trakt_id', ''), 'Trakt Client ID'),
                ('trakt_client_secret', data.get('trakt_secret', ''), 'Trakt Client Secret'),
                ('default_behavior', data.get('aiostreams_behavior', 'show_streams'), 'Default Behavior'),
                ('subtitle_languages', data.get('aiostreams_subtitles', ''), 'Subtitle Languages'),
                ('autoplay_next_episode', selections.get('upnext'), 'Autoplay Next Episode'),
            ]

            failed_settings = []
            for setting_key, setting_value, description in settings_to_apply:
                if not apply_setting(aio, setting_key, setting_value, description):
                    failed_settings.append(setting_key)

            if failed_settings:
                xbmc.log(f"[Onboarding] WARNING: Failed to apply {len(failed_settings)} settings: {', '.join(failed_settings)}", xbmc.LOGWARNING)

            # Close settings to ensure they are saved
            xbmc.log("[Onboarding] Closing AIOStreams addon to persist settings...", xbmc.LOGINFO)
            del aio
            time.sleep(3)  # Wait for settings to be written to disk

            # Verify settings were saved by reloading addon
            progress.update(24, f"Step {current_step}/{total_steps}: Verifying settings...")
            aio_verify = ensure_addon('plugin.video.aiostreams')
            if aio_verify:
                # Verify multiple settings were saved
                saved_host = aio_verify.getSetting('aiostreams_host')
                saved_uuid = aio_verify.getSetting('aiostreams_uuid')
                saved_trakt_id = aio_verify.getSetting('trakt_client_id')
                saved_behavior = aio_verify.getSetting('default_behavior')

                verification_results = []
                if saved_host:
                    verification_results.append(f"Host: {saved_host[:30]}...")
                if saved_uuid:
                    verification_results.append(f"UUID: {saved_uuid[:20]}...")
                if saved_trakt_id:
                    verification_results.append("Trakt ID: [SET]")
                if saved_behavior:
                    verification_results.append(f"Behavior: {saved_behavior}")

                if verification_results:
                    xbmc.log(f"[Onboarding] Settings verified saved: {'; '.join(verification_results)}", xbmc.LOGINFO)
                else:
                    xbmc.log("[Onboarding] WARNING: No settings were verified as saved! They may not have persisted.", xbmc.LOGWARNING)
                    xbmcgui.Dialog().notification("Settings Warning", "Settings may not have saved. Check logs.", xbmcgui.NOTIFICATION_WARNING, 3000)

                del aio_verify
                time.sleep(1)

            # Call integrations/retrieve manifest
            progress.update(25, f"Step {current_step}/{total_steps}: Retrieving Manifest...")
            xbmc.log("[Onboarding] Calling retrieve_manifest...", xbmc.LOGINFO)
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=retrieve_manifest)')
            # Wait for manifest retrieval to complete (silent)
            time.sleep(8)

            # Call integrations/authorize trakt (silent, user can do this later if needed)
            progress.update(28, f"Step {current_step}/{total_steps}: Configuring Trakt integration...")
            xbmc.log("[Onboarding] Calling trakt_auth...", xbmc.LOGINFO)
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=trakt_auth)')
            # Give it time to process in background
            time.sleep(5)  # Increased wait time for Trakt auth

            notify(f"Step {current_step}/{total_steps}: AIOStreams ready ✓")
            xbmc.log("[Onboarding] AIOStreams configuration complete", xbmc.LOGINFO)
            time.sleep(0.5)

        except Exception as e:
            xbmc.log(f"[Onboarding] AIOStreams config error: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Setup Error", f"AIOStreams configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 2. If requested, Install YouTube plugin from kodi repository (or update if already installed)
    if selections.get('youtube'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Installing YouTube', xbmc.LOGINFO)
        notify(f"Step {current_step}/{total_steps}: Installing YouTube...")
        if install_with_wait('plugin.video.youtube', progress, 35, 45, update_if_exists=True):
            try:
                notify(f"Step {current_step}/{total_steps}: Configuring YouTube...")
                yt = ensure_addon('plugin.video.youtube')
                if yt:
                    xbmc.log("[Onboarding] Applying YouTube settings...", xbmc.LOGINFO)
                    # Turn off general/enable setup wizard
                    apply_setting(yt, 'youtube.folder.my_subscriptions.show', 'false', 'Subscriptions Folder')
                    # Enter API Key in API/API Key
                    apply_setting(yt, 'youtube.api.key', data.get('yt_key', ''), 'YouTube API Key')
                    # Enter API ID in API/API ID
                    apply_setting(yt, 'youtube.api.id', data.get('yt_id', ''), 'YouTube API ID')
                    # Enter API Secret in API/API Secret
                    apply_setting(yt, 'youtube.api.secret', data.get('yt_secret', ''), 'YouTube API Secret')
                    # Turn on API/allow developer keys
                    apply_setting(yt, 'youtube.api.enable', 'true', 'Enable API')
                    del yt
                    notify(f"Step {current_step}/{total_steps}: YouTube ready ✓")
                    xbmc.log("[Onboarding] YouTube configuration complete", xbmc.LOGINFO)
                    time.sleep(0.5)
                else:
                    xbmc.log(f"[Onboarding] Failed to configure YouTube - addon not loadable", xbmc.LOGERROR)
            except Exception as e:
                xbmc.log(f"[Onboarding] YouTube config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"YouTube configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 3. If requested, Install Up Next plugin from kodi repository (or update if already installed)
    if selections.get('upnext'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Installing UpNext', xbmc.LOGINFO)
        notify(f"Step {current_step}/{total_steps}: Installing UpNext...")
        if install_with_wait('service.upnext', progress, 52, 60, update_if_exists=True):
            try:
                notify(f"Step {current_step}/{total_steps}: Configuring UpNext...")
                un = ensure_addon('service.upnext')
                if un:
                    xbmc.log("[Onboarding] Applying UpNext settings...", xbmc.LOGINFO)
                    # Change interface/set display mode for notifications to Simple
                    apply_setting(un, 'simpleMode', '1', 'Simple Mode')  # 1 = Simple, 0 = Fancy
                    # Enable interface/show a stop button instead of a close button
                    apply_setting(un, 'stopAfterClose', 'true', 'Stop After Close')
                    # Change behaviour/default action when nothing selected to 'Play Next'
                    apply_setting(un, 'autoPlayMode', '0', 'Auto Play Mode')  # 0 = Auto play next episode
                    del un
                    notify(f"Step {current_step}/{total_steps}: UpNext ready ✓")
                    xbmc.log("[Onboarding] UpNext configuration complete", xbmc.LOGINFO)
                    time.sleep(0.5)
                else:
                    xbmc.log(f"[Onboarding] Failed to configure UpNext - addon not loadable", xbmc.LOGERROR)
            except Exception as e:
                xbmc.log(f"[Onboarding] UpNext config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"UpNext configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 4. If requested install IPTV Simple Player from kodi repository (or update if already installed)
    if selections.get('iptv'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Installing IPTV Simple', xbmc.LOGINFO)
        notify(f"Step {current_step}/{total_steps}: Installing IPTV Simple...")
        if install_with_wait('pvr.iptvsimple', progress, 67, 75, update_if_exists=True):
            try:
                notify(f"Step {current_step}/{total_steps}: Configuring IPTV Simple...")
                iptv = ensure_addon('pvr.iptvsimple')
                if iptv:
                    xbmc.log("[Onboarding] Applying IPTV Simple settings...", xbmc.LOGINFO)
                    # Configure M3U URL if provided
                    m3u_url = data.get('iptv_m3u', '')
                    if m3u_url:
                        apply_setting(iptv, 'm3uPathType', '1', 'M3U Path Type')  # 1 = Remote path (URL)
                        apply_setting(iptv, 'm3uUrl', m3u_url, 'M3U URL')

                    # Configure EPG URL if provided
                    epg_url = data.get('iptv_epg', '')
                    if epg_url:
                        apply_setting(iptv, 'epgPathType', '1', 'EPG Path Type')  # 1 = Remote path (URL)
                        apply_setting(iptv, 'epgUrl', epg_url, 'EPG URL')

                    del iptv
                    notify(f"Step {current_step}/{total_steps}: IPTV Simple ready ✓")
                    xbmc.log('[Onboarding] IPTV Simple Player configuration complete', xbmc.LOGINFO)
                    time.sleep(0.5)
                else:
                    xbmc.log(f"[Onboarding] Failed to configure IPTV Simple - addon not loadable", xbmc.LOGERROR)
            except Exception as e:
                xbmc.log(f"[Onboarding] IPTV config error: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().notification("Setup Error", f"IPTV configuration failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)

    # 5. If requested install IMVDb plugin from my repository (or update if already installed)
    if selections.get('imvdb'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Installing IMVDb', xbmc.LOGINFO)
        notify(f"Step {current_step}/{total_steps}: Installing IMVDb...")
        if install_with_wait('plugin.video.imvdb', progress, 82, 87, update_if_exists=True):
            try:
                notify(f"Step {current_step}/{total_steps}: Configuring IMVDb...")
                im = ensure_addon('plugin.video.imvdb')
                if im:
                    xbmc.log("[Onboarding] Applying IMVDb settings...", xbmc.LOGINFO)
                    # In settings, set IMVDb API Key
                    apply_setting(im, 'api_key', data.get('imvdb_key', ''), 'IMVDb API Key')
                    del im
                    notify(f"Step {current_step}/{total_steps}: IMVDb ready")
                    xbmc.log("[Onboarding] IMVDb configuration complete", xbmc.LOGINFO)
                    time.sleep(0.5)
                else:
                    xbmc.log(f"[Onboarding] Failed to configure IMVDb - addon not loadable", xbmc.LOGERROR)
                    notify("IMVDb configuration failed")
            except Exception as e:
                xbmc.log(f"[Onboarding] IMVDb config error: {e}", xbmc.LOGERROR)
                notify(f"IMVDb config error: {str(e)}")
        else:
            xbmc.log(f"[Onboarding] IMVDb installation timed out", xbmc.LOGWARNING)
            notify("IMVDb installation timed out")

    # 6. If TMDB helper players are selected, save a copy of the zip file to the special://home directory
    if selections.get('tmdbh'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Setting up TMDB Helper Players', xbmc.LOGINFO)
        notify(f"Step {current_step}/{total_steps}: Setting up TMDB Helper Players...")
        try:
            src = os.path.join(os.path.dirname(ADDON_PATH), "TMDB Helper Players", "tmdbhelper-players.zip")
            # Fallback path for development environment
            if not xbmcvfs.exists(src):
                src = "/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/TMDB Helper Players/tmdbhelper-players.zip"

            dst = xbmcvfs.translatePath("special://home/tmdbhelper-players.zip")
            if xbmcvfs.exists(src):
                xbmcvfs.copy(src, dst)
                notify(f"Step {current_step}/{total_steps}: TMDB Helper Players ready ✓")
                time.sleep(0.5)
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
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Installing AIODI Skin', xbmc.LOGINFO)
        notify(f"Step {current_step}/{total_steps}: Installing AIODI Skin...")

        # Check if already installed first
        skin_installed = xbmc.getCondVisibility('System.HasAddon(skin.AIODI)')

        if not skin_installed:
            xbmc.log('[Onboarding] Installing skin with auto-approval', xbmc.LOGINFO)
            xbmc.executebuiltin('InstallAddon(skin.AIODI)')

            # Auto-approve installation dialog
            time.sleep(0.5)  # Wait for dialog
            xbmc.executebuiltin('SendClick(12)')  # Click Yes
            time.sleep(0.2)

            # Wait up to 180 seconds for skin to install
            install_result = False
            for i in range(360):  # 180 seconds, check every 0.5s
                if i % 20 == 0:  # Update every 10 seconds
                    elapsed = i * 0.5
                    notify(f"Installing skin... ({int(elapsed)}s)")

                if xbmc.getCondVisibility('System.HasAddon(skin.AIODI)'):
                    install_result = True
                    xbmc.log('[Onboarding] Skin installation detected', xbmc.LOGINFO)
                    break
                time.sleep(0.5)

            skin_installed = xbmc.getCondVisibility('System.HasAddon(skin.AIODI)')
        else:
            install_result = True
            xbmc.log('[Onboarding] Skin already installed', xbmc.LOGINFO)
            notify("Skin already installed")

        if install_result or skin_installed:
            if not install_result and skin_installed:
                xbmc.log('[Onboarding] Skin installation timed out but skin is actually installed', xbmc.LOGINFO)
            else:
                xbmc.log('[Onboarding] Skin installed successfully', xbmc.LOGINFO)

            notify(f"Step {current_step}/{total_steps}: AIODI Skin ready ✓")
            xbmc.log('[Onboarding] Skin installation complete, will restart Kodi for user to activate', xbmc.LOGINFO)
        else:
            xbmc.log('[Onboarding] Skin installation failed - not found after timeout', xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Setup Warning", "AIODI skin installation failed", xbmcgui.NOTIFICATION_WARNING)
    else:
        xbmc.log('[Onboarding] Skin installation not requested (selections.get("skin") returned False/None)', xbmc.LOGINFO)

    notify(f"Setup complete! All {total_steps} steps finished.")
    xbmc.log(f'[Onboarding] Installation complete. Processed {current_step}/{total_steps} steps.', xbmc.LOGINFO)
    time.sleep(1)

    # Show final completion message with next steps
    final_msg = (
        "[B]Setup Complete - Next Steps[/B]\n\n"
        "1. Switch to AIODI skin:\n   Settings > Interface > Skin > AIODI\n\n"
        "2. Configure widgets:\n   Use widget manager (left from Settings icon)\n\n"
        "3. Log into YouTube:\n   Settings > Add-ons > Video add-ons > YouTube > Configure\n\n"
        "4. Restart Kodi one more time to finalize\n\n"
        "Restarting Kodi now..."
    )
    xbmcgui.Dialog().ok("AIODI Setup Complete", final_msg)

    # Restart Kodi to ensure all changes take effect
    xbmc.log('[Onboarding] Restarting Kodi to apply changes...', xbmc.LOGINFO)
    xbmc.executebuiltin('RestartApp')

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
