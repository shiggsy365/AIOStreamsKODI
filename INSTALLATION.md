# AIOStreams Kodi Addon - Installation Guide

## Quick Installation (Recommended)

### Step 1: Install Repository
1. Download [repository.aiostreams.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/repository.aiostreams.zip)
2. In Kodi, go to: **Settings → Add-ons → Install from zip file**
3. Browse to the downloaded `repository.aiostreams.zip`
4. Wait for "Add-on enabled" notification

### Step 2: Install AIOStreams
1. Go to: **Settings → Add-ons → Install from repository**
2. Select **AIOStreams Repository**
3. Choose **Video add-ons**
4. Select **AIOStreams**
5. Click **Install**
6. Wait for dependencies to install

### Step 3: Configure
1. Go to: **Add-ons → Video add-ons → AIOStreams**
2. Right-click and select **Settings**
3. Configure your AIOStreams server URL
4. (Optional) Configure Trakt integration

---

## Manual Installation

### Download Direct
Download the addon zip directly:
- **Latest Version**: [plugin.video.aiostreams.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/plugin.video.aiostreams.zip)

### Install in Kodi
1. In Kodi, go to: **Settings → Add-ons → Install from zip file**
2. Browse to the downloaded `plugin.video.aiostreams.zip`
3. Wait for installation to complete

---

## GitHub Raw URLs (for advanced users)

If you want to set up the repository manually in Kodi's file manager:

### Repository Files
```
https://raw.githubusercontent.com/shiggsy365/AIOStreamsKODI/main/repo/addons.xml
https://raw.githubusercontent.com/shiggsy365/AIOStreamsKODI/main/repo/addons.xml.md5
https://raw.githubusercontent.com/shiggsy365/AIOStreamsKODI/main/repo/plugin.video.aiostreams.zip
```

### Direct Addon Download
```
https://github.com/shiggsy365/AIOStreamsKODI/raw/main/plugin.video.aiostreams.zip
```

---

## Post-Installation Setup

### 1. Configure AIOStreams Server
1. Open addon settings: **Settings → Add-on Settings**
2. Under **General**, enter your **AIOStreams Base URL**
3. Test connection: **Advanced → Maintenance → Test AIOStreams Connection**

### 2. Setup Trakt (Optional but Recommended)
1. Go to [trakt.tv](https://trakt.tv) and create an account
2. Create a new application at: https://trakt.tv/oauth/applications/new
   - **Name**: AIOStreams Kodi
   - **Redirect URI**: `urn:ietf:wg:oauth:2.0:oob`
   - **Permissions**: Select all `/scrobble`, `/sync/`, and `/recommendations`
3. Copy the **Client ID** and **Client Secret**
4. In addon settings, go to **Trakt** category
5. Enter **Client ID** and **Client Secret**
6. Click **Authorize Trakt**
7. Follow the on-screen instructions

### 3. Enable Keyboard Shortcuts (Optional)
1. Copy `keymap.xml.template` from addon folder to:
   - **Windows**: `%APPDATA%\Kodi\userdata\keymaps\aiostreams.xml`
   - **Linux**: `~/.kodi/userdata/keymaps/aiostreams.xml`
   - **macOS**: `~/Library/Application Support/Kodi/userdata/keymaps/aiostreams.xml`
2. Restart Kodi
3. Shortcuts are now active:
   - **Q** - Toggle Watchlist
   - **W** - Mark as Watched
   - **I** - Show Info
   - **S** - Similar Content
   - **A** - Quick Actions Menu

### 4. Customize Settings
Explore the settings to customize your experience:
- **General**: Quality preferences, playback behavior
- **User Interface**: Progress bars, color coding, badges
- **Advanced**: Performance tuning, cache settings
- **Trakt**: Scrobbling, sync options

---

## Updating the Addon

### Via Repository (Automatic)
If you installed via the repository, updates are automatic:
1. Kodi checks for updates periodically
2. New versions install automatically
3. Check version: **Add-ons → Video add-ons → AIOStreams → right-click → Information**

### Manual Update
1. Download the latest `plugin.video.aiostreams.zip`
2. Install over existing version (Kodi will upgrade)
3. No need to reconfigure settings (they're preserved)

---

## Troubleshooting

### "Unable to connect" errors
1. Verify your AIOStreams Base URL is correct
2. Test connection: **Advanced → Test AIOStreams Connection**
3. Check network/firewall settings

### Trakt not working
1. Verify Client ID and Secret are correct
2. Re-authorize: **Trakt → Authorize Trakt**
3. Check token hasn't expired

### Streams not appearing
1. Clear cache: **Advanced → Clear Cache**
2. Check quality filters aren't too restrictive
3. Try different content

### Performance issues
1. Disable color coding if Trakt is slow
2. Increase cache expiry
3. Reduce max streams to show

---

## Custom Search Integration

For Kodi skins that provide a custom search option, you can use the AIOStreams search directly:

### Custom Search Path
```
plugin://plugin.video.aiostreams/?action=search&content_type=both&query=
```

This allows you to integrate AIOStreams search into your skin's search functionality. The addon will handle the search and display results in a poster view.

### Search Parameters
- `action=search` - Required
- `content_type` - Optional: `movie`, `series`, or `both` (default)
- `query` - The search term (appended to URL)

### Example Usage
```
plugin://plugin.video.aiostreams/?action=search&content_type=movie&query=inception
plugin://plugin.video.aiostreams/?action=search&content_type=series&query=breaking bad
```

---

## Features Documentation

For complete feature documentation, see:
- **README.md** in the repository
- Or online at: [GitHub README.md](https://github.com/shiggsy365/AIOStreamsKODI/blob/main/README.md)

---


- **GitHub Issues**: [Report a bug](https://github.com/shiggsy365/AIOStreamsKODI/issues)
- **Documentation**: See FEATURES.md for detailed feature guide

---

**Enjoy AIOStreams!** 🎬
