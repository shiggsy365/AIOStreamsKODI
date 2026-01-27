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

def auto_approve_dialog(timeout=10, step_name=""):
    """Repeatedly try to click 'Yes/OK' on confirmation dialogs (Legacy Fallback)"""
    xbmc.log(f'[Onboarding] {step_name}: Watching for confirmation dialogs...', xbmc.LOGINFO)
    for i in range(timeout * 2): # 0.5s per iteration
        if xbmc.getCondVisibility('Window.IsActive(yesnodialog)') or \
           xbmc.getCondVisibility('Window.IsActive(okdialog)'):
            xbmc.executebuiltin('SendClick(11)') # Yes/OK
            xbmc.executebuiltin('SendClick(12)') 
            xbmc.executebuiltin('SendClick(10)')
            time.sleep(1)
        time.sleep(0.5)
    return True

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

def inject_dependencies(selections):
    """Dynamically add selected addons to requires list in addon.xml to force Kodi to install them"""
    try:
        xml_path = os.path.join(ADDON_PATH, 'addon.xml')
        if not os.path.exists(xml_path):
            xbmc.log(f"[Onboarding] addon.xml not found at {xml_path}", xbmc.LOGERROR)
            return

        import xml.etree.ElementTree as ET
        tree = ET.parse(xml_path)
        root = tree.getroot()
        requires = root.find('requires')

        if requires is None:
            requires = ET.SubElement(root, 'requires')

        # List of addons to inject based on selections
        target_addons = [('plugin.video.aiostreams', True)] # Always needed
        if selections.get('skin'): target_addons.append(('skin.AIODI', True))
        if selections.get('youtube'): target_addons.append(('plugin.video.youtube', True))
        if selections.get('upnext'): target_addons.append(('service.upnext', True))
        if selections.get('iptv'): target_addons.append(('pvr.iptvsimple', True))
        if selections.get('imvdb'): target_addons.append(('plugin.video.imvdb', True))
        if selections.get('tmdbh'): target_addons.append(('script.module.tmdbhelper', True))

        existing_deps = [imp.get('addon') for imp in requires.findall('import')]
        
        # Aggressive version bumping to force Kodi re-scan
        version = root.get('version', '1.0.0')
        version_parts = version.split('.')
        try:
            # Increment the last part of the version
            version_parts[-1] = str(int(version_parts[-1]) + 1)
            new_version = ".".join(version_parts)
            root.set('version', new_version)
            xbmc.log(f"[Onboarding] Version bumped to {new_version} to force re-scan", xbmc.LOGINFO)
        except:
            root.set('version', version + ".1")

        modified = True
        for addon_id, needed in target_addons:
            if needed and addon_id not in existing_deps:
                ET.SubElement(requires, 'import', addon=addon_id)
                xbmc.log(f"[Onboarding] Injected dependency: {addon_id}", xbmc.LOGINFO)

        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        xbmc.log("[Onboarding] addon.xml updated with new dependencies", xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log(f"[Onboarding] Failed to inject dependencies: {e}", xbmc.LOGERROR)
    return False

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

    # Wait and auto-approve
    auto_approve_dialog(timeout=15, step_name=f"Install {addon_id}")

    # Wait loop with progress updates (max_wait_time seconds)

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
                # Save all settings AND selections to cache
                cache_data = self.data.copy()
                cache_data.update(self.selections)
                save_cache(cache_data)

                # Trigger Phase 1: Injection & Restart
                xbmc.log("[Onboarding] Phase 1: Injecting dependencies and triggering restart", xbmc.LOGINFO)
                inject_dependencies(self.selections)
                
                msg = (
                    "[B]Phase 1 Complete[/B]\n\n"
                    "Settings saved and components injected.\n"
                    "Kodi must now restart to install the missing plugins.\n\n"
                    "[I]Please select YES on the native 'Install dependencies' prompt after Kodi starts.[/I]"
                )
                xbmcgui.Dialog().ok("AIODI Setup", msg)
                
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
            progress.update(base_pct, f"Installing dependencies ({idx}/{total_deps}): {dep.split('.')[-1]}...")
            xbmc.executebuiltin(f'InstallAddon({dep})')

            # Auto-approve
            auto_approve_dialog(timeout=10, step_name=f"Dep {dep}")

            # Wait for installation with timeout and progress updates

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

def run_installer(selections, data, is_stage_2=False):
    # Use notifications instead of progress dialog
    def notify(message):
        xbmcgui.Dialog().notification("AIODI Setup", message, xbmcgui.NOTIFICATION_INFO, 3000)

    if not is_stage_2:
        # Phase 1: Just restart
        xbmc.log("[Onboarding] Stage 1 restart triggered", xbmc.LOGINFO)
        # Force Kodi to re-scan addon.xml
        xbmc.executebuiltin('UpdateLocalAddons')
        time.sleep(1)
        xbmc.executebuiltin('RestartApp')
        return

    notify("Phase 2: Configuring components...")
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

    # Sync repositories first to ensure newest versions are visible
    xbmc.log("[Onboarding] Triggering repository update and forced refresh...", xbmc.LOGINFO)
    xbmc.executebuiltin('UpdateLocalAddons')
    time.sleep(3)
    xbmc.executebuiltin('UpdateAddonRepos')
    # Force a database update for the addon database specifically if possible
    xbmc.executebuiltin('UpdateAddonRepos') 
    
    # Give it a substantial amount of time to pull the latest metadata
    notify("Refreshing Addon Repositories (may take 20s)...")
    for i in range(40):
        if progress.iscanceled(): break
        if i % 10 == 0:
            xbmc.log(f"[Onboarding] Repo update wait: {i*0.5}s", xbmc.LOGINFO)
        time.sleep(0.5)

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

    # Total estimated steps for configuration
    total_steps = 0
    if selections.get('aiostreams', True): total_steps += 1
    if selections.get('youtube'): total_steps += 1
    if selections.get('upnext'): total_steps += 1
    if selections.get('iptv'): total_steps += 1
    if selections.get('imvdb'): total_steps += 1
    if selections.get('tmdbh'): total_steps += 1
    if selections.get('skin'): total_steps += 1

    current_step = 0

    # 1. Configure AIOStreams Plugin
    if selections.get('aiostreams', True):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Configuring AIOStreams', xbmc.LOGINFO)
        try:
            notify(f"Configuring AIOStreams...")
            aio = ensure_addon('plugin.video.aiostreams')
            if aio:
                # Set Main Settings
                apply_setting(aio, 'aiostreams_host', data.get('aiostreams_host', ''), 'AIOStreams Host')
                apply_setting(aio, 'aiostreams_uuid', data.get('aiostreams_uuid', ''), 'AIOStreams UUID')
                apply_setting(aio, 'aiostreams_password', data.get('aiostreams_password', ''), 'AIOStreams Password')
                apply_setting(aio, 'default_behavior', data.get('aiostreams_behavior', 'show_streams'), 'Default Behavior')
                apply_setting(aio, 'subtitle_languages', data.get('aiostreams_subtitles', ''), 'Subtitles')
                
                # UpNext Integration
                if selections.get('upnext'):
                    apply_setting(aio, 'autoplay_next_episode', 'true', 'Enable UpNext')
                
                # Trakt Settings
                apply_setting(aio, 'trakt_client_id', data.get('trakt_id', ''), 'Trakt Client ID')
                apply_setting(aio, 'trakt_client_secret', data.get('trakt_secret', ''), 'Trakt Client Secret')
                
                # Refresh local versions
                xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=retrieve_manifest)')
                time.sleep(2)
                
                notify(f"AIOStreams configured ✓")
                del aio
            else:
                xbmc.log("[Onboarding] Could not find AIOStreams plugin for configuration", xbmc.LOGERROR)
        except Exception as e:
            xbmc.log(f"[Onboarding] AIOStreams config error: {e}", xbmc.LOGERROR)

    # 2. Configure YouTube plugin
    if selections.get('youtube') and xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Configuring YouTube', xbmc.LOGINFO)
        try:
            notify(f"Configuring YouTube...")
            yt = ensure_addon('plugin.video.youtube')
            if yt:
                apply_setting(yt, 'youtube.api.key', data.get('yt_key', ''), 'YouTube API Key')
                apply_setting(yt, 'youtube.api.id', data.get('yt_id', ''), 'YouTube API ID')
                apply_setting(yt, 'youtube.api.secret', data.get('yt_secret', ''), 'YouTube API Secret')
                apply_setting(yt, 'youtube.api.enable', 'true', 'Enable API')
                del yt
                notify(f"YouTube configured ✓")
        except Exception as e:
            xbmc.log(f"[Onboarding] YouTube config error: {e}", xbmc.LOGERROR)

    # 3. Configure Up Next plugin
    if selections.get('upnext') and xbmc.getCondVisibility('System.HasAddon(service.upnext)'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Configuring UpNext', xbmc.LOGINFO)
        try:
            notify(f"Configuring UpNext...")
            un = ensure_addon('service.upnext')
            if un:
                apply_setting(un, 'simpleMode', '1', 'Simple Mode')
                apply_setting(un, 'autoPlayMode', '0', 'Auto Play Mode')
                del un
                notify(f"UpNext configured ✓")
        except Exception as e:
            xbmc.log(f"[Onboarding] UpNext config error: {e}", xbmc.LOGERROR)

    # 4. Configure IPTV Simple Player
    if selections.get('iptv') and xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Configuring IPTV Simple', xbmc.LOGINFO)
        try:
            notify(f"Configuring IPTV Simple...")
            pvr_data_path = xbmcvfs.translatePath('special://userdata/addon_data/pvr.iptvsimple/')
            if not xbmcvfs.exists(pvr_data_path): xbmcvfs.mkdirs(pvr_data_path)
            
            instance_file = os.path.join(pvr_data_path, 'instance-settings-1.xml')
            import xml.etree.ElementTree as ET
            
            if xbmcvfs.exists(instance_file):
                tree = ET.parse(instance_file)
                root = tree.getroot()
            else:
                root = ET.Element('settings', version='2')
                ET.SubElement(root, 'setting', id='kodi_addon_instance_name').text = 'AIODI IPTV'

            # M3U URL
            m3u = data.get('iptv_m3u', '')
            if m3u:
                s_type = root.find(".//setting[@id='m3uPathType']")
                if s_type is None: s_type = ET.SubElement(root, 'setting', id='m3uPathType')
                s_type.text = '1'
                s_url = root.find(".//setting[@id='m3uUrl']")
                if s_url is None: s_url = ET.SubElement(root, 'setting', id='m3uUrl')
                s_url.text = m3u
            
            # EPG URL
            epg = data.get('iptv_epg', '')
            if epg:
                s_type = root.find(".//setting[@id='epgPathType']")
                if s_type is None: s_type = ET.SubElement(root, 'setting', id='epgPathType')
                s_type.text = '1'
                s_url = root.find(".//setting[@id='epgUrl']")
                if s_url is None: s_url = ET.SubElement(root, 'setting', id='epgUrl')
                s_url.text = epg

            tree = ET.ElementTree(root)
            with open(instance_file, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=True)
            
            notify(f"IPTV Simple configured ✓")
            xbmc.executebuiltin('UpdateLocalAddons')
        except Exception as e:
            xbmc.log(f"[Onboarding] IPTV config error: {e}", xbmc.LOGERROR)

    # 5. Configure IMVDb plugin
    if selections.get('imvdb') and xbmc.getCondVisibility('System.HasAddon(plugin.video.imvdb)'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Configuring IMVDb', xbmc.LOGINFO)
        try:
            notify(f"Configuring IMVDb...")
            im = ensure_addon('plugin.video.imvdb')
            if im:
                apply_setting(im, 'api_key', data.get('imvdb_key', ''), 'IMVDb API Key')
                del im
                notify(f"IMVDb configured ✓")
        except Exception as e:
            xbmc.log(f"[Onboarding] IMVDb config error: {e}", xbmc.LOGERROR)

    # 6. TMDB Helper Players
    if selections.get('tmdbh'):
        current_step += 1
        xbmc.log(f'[Onboarding] Step {current_step}/{total_steps}: Setting up TMDB Helper Players', xbmc.LOGINFO)
        try:
            src = os.path.join(os.path.dirname(ADDON_PATH), "TMDB Helper Players", "tmdbhelper-players.zip")
            if not xbmcvfs.exists(src):
                src = "/home/jon/Downloads/AIOStreamsKODI/AIOStreamsKODI/TMDB Helper Players/tmdbhelper-players.zip"
            
            dst = xbmcvfs.translatePath("special://home/tmdbhelper-players.zip")
            if xbmcvfs.exists(src):
                xbmcvfs.copy(src, dst)
                notify(f"TMDB Players ready ✓")
        except Exception as e:
            xbmc.log(f"[Onboarding] TMDB Helper error: {e}", xbmc.LOGERROR)

    # 7. Skin Installation & Switching
    if selections.get('skin'):
        current_step += 1
        notify(f"Finalizing Skin...")
        if xbmc.getCondVisibility('System.HasAddon(skin.AIODI)'):
            notify("AIODI Skin ready ✓")
        else:
            notify("Skin missing - will retry on next run")

    xbmc.log(f'[Onboarding] Configuration complete. Processed {current_step}/{total_steps} steps.', xbmc.LOGINFO)
    notify("Setup complete! All steps finished.")
    time.sleep(2)

    # Show final completion message
    final_msg = (
        "[B]Setup Complete![/B]\n\n"
        "All components have been configured with your settings.\n\n"
        "1. Switch to AIODI skin in Settings > Interface.\n"
        "2. Restart Kodi one last time to finalize everything.\n\n"
        "Enjoy your new setup!"
    )
    xbmcgui.Dialog().ok("AIODI Setup Complete", final_msg)
    xbmc.executebuiltin('RestartApp')

def run_guided_installer(selections):
    """Sequential navigator that guides the user through official Kodi installation pages"""
    target_addons = [
        ('plugin.video.aiostreams', "AIOStreams"),
        ('plugin.video.youtube', "YouTube"),
        ('service.upnext', "UpNext"),
        ('pvr.iptvsimple', "IPTV Simple"),
        ('plugin.video.imvdb', "IMVDb"),
        ('script.module.tmdbhelper', "TMDB Helper"),
        ('skin.AIODI', "AIODI Skin")
    ]
    
    active_addons = [(id, name) for id, name in target_addons if selections.get(name.lower().replace(" ", ""), True)]
    
    # Force a repository refresh before starting
    xbmc.log("[Onboarding] Refreshing repositories...", xbmc.LOGINFO)
    xbmc.executebuiltin('UpdateAddonRepos')
    time.sleep(1)

    for addon_id, name in active_addons:
        if not xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            msg = (
                f"[B]Guided Setup: {name}[/B]\n\n"
                f"I will now trigger the official installation popup for {name}.\n\n"
                "1. Click [B]YES / INSTALL[/B] on the popup.\n"
                "2. If prompted for dependencies, select [B]OK[/B].\n"
                "3. Once finished, return here (back out) to continue."
            )
            xbmcgui.Dialog().ok("AIODI Setup", msg)
            
            # Direct Installation Trigger
            xbmc.executebuiltin(f'InstallAddon({addon_id})')
            
            # Detect install (Wait up to 120s)
            for _ in range(240):
                if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
                    xbmc.executebuiltin(f'EnableAddon({addon_id})')
                    break
                time.sleep(0.5)
            
            if not xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
                if not xbmcgui.Dialog().yesno("Addon Missing", f"{name} was not detected. Continue to next step?"):
                    return False
    return True

def run():
    cache = load_cache()
    
    # Check if we have cached data (Phase 2 candidate)
    if cache.get('aiostreams_host'):
        aiostreams_installed = xbmc.getCondVisibility('System.HasAddon(plugin.video.aiostreams)')
        
        if aiostreams_installed:
            xbmc.log("[Onboarding] Stage 2 detected: Components installed, applying settings", xbmc.LOGINFO)
            # Use simple yes/no to confirm Phase 2 vs fresh start
            if xbmcgui.Dialog().yesno("AIODI Setup", "Settings detected and components installed.\n\nApply configuration now?"):
                run_installer(cache, cache, is_stage_2=True)
                return
        else:
            # Cache exists but AIOStreams is missing -> GUIDED Flow
            xbmc.log("[Onboarding] Resume detected: Entering Guided Installation Mode", xbmc.LOGINFO)
            
            options = ["Start Guided Installation (Recommended)", "Exit Setup"]
            choice = xbmcgui.Dialog().select("Finish AIODI Installation", options)
            
            if choice == 0:
                if run_guided_installer(cache):
                    if xbmc.getCondVisibility('System.HasAddon(plugin.video.aiostreams)'):
                        xbmcgui.Dialog().ok("Success", "Plugins ready! Finalizing configuration...")
                        run_installer(cache, cache, is_stage_2=True)
                return
            else:
                return

    # [STATE: FRESH/START]
    form = InputWindow('onboarding_input.xml', ADDON_PATH, 'Default', '1080i')
    form.doModal()
    data = form.data
    selections = form.selections
    cancelled = form.cancelled
    del form
    
    if cancelled: return

    # Save to local cache first
    cache_data = data.copy()
    cache_data.update(selections)
    save_cache(cache_data)

    # Perform injection and trigger Stage 1 Restart
    inject_dependencies(selections)
    run_installer(selections, data, is_stage_2=False)

if __name__ == '__main__':
    run()

