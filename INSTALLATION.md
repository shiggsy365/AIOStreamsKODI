# AIOStreams Kodi Addon - Installation Guide

Complete installation and configuration guide for AIOStreams Kodi Addon.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Methods](#installation-methods)
   - [Method 1: Repository Installation (Recommended)](#method-1-repository-installation-recommended)
   - [Method 2: Manual Zip Installation](#method-2-manual-zip-installation)
3. [Initial Configuration](#initial-configuration)
4. [AIOStreams Backend Setup](#aiostreams-backend-setup)
5. [Trakt Integration Setup](#trakt-integration-setup)
6. [TMDBHelper Integration](#tmdbhelper-integration)
7. [Advanced Configuration](#advanced-configuration)
8. [Keyboard Shortcuts Setup](#keyboard-shortcuts-setup-optional)
9. [Troubleshooting](#troubleshooting)
10. [Updating the Addon](#updating-the-addon)

---

## Prerequisites

### Required

1. **Kodi 19+ (Matrix, Nexus, or Omega)**
   - Download from: [kodi.tv/download](https://kodi.tv/download)
   - Python 3 addon support required

2. **AIOStreams Backend**
   - Self-hosted instance or hosted service (e.g., ElfHosted)
   - Minimum configuration required:
     - At least one stream scraper
     - Search provider (recommend: AIOMetadata)
     - Metadata source (recommend: AIOMetadata)
   - GitHub: [github.com/Viren070/aiostreams](https://github.com/Viren070/aiostreams)

### Recommended

3. **AIOMetadata** (for rich metadata and search)
   - Provides TMDb/TVDb integration
   - GitHub: [github.com/cedya77/aiometadata](https://github.com/cedya77/aiometadata)
   - Configure as both search and metadata source in AIOStreams

4. **Trakt Account** (for sync features)
   - Free account: [trakt.tv](https://trakt.tv)
   - Tracks watch history, progress, and recommendations

### Optional

5. **TMDBHelper** (for unified content discovery)
   - Available from official Kodi repository
   - Enhanced content browsing and unified player interface

---

## Installation Methods

### Method 1: Repository Installation (Recommended)

Installing via repository ensures automatic updates and easy maintenance.

#### Step 1: Enable Unknown Sources

1. Open Kodi
2. Navigate to: **Settings → System → Add-ons**
3. Enable: **Unknown sources**
4. Click **Yes** when prompted with security warning

#### Step 2: Download Repository

Download the repository zip file:
- **URL**: [repository.aiostreams.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/repository.aiostreams.zip)
- Save to a location accessible from Kodi (Downloads folder, USB drive, etc.)

#### Step 3: Install Repository

1. In Kodi, go to: **Settings → Add-ons**
2. Click: **Install from zip file**
3. Browse to the downloaded `repository.aiostreams.zip`
4. Select the file and wait for installation
5. You should see: **"Add-on enabled"** notification

#### Step 4: Install AIOStreams Addon

1. Stay in: **Settings → Add-ons**
2. Click: **Install from repository**
3. Select: **AIOStreams Repository**
4. Navigate to: **Video add-ons**
5. Select: **AIOStreams**
6. Click: **Install**
7. Dependencies will install automatically (script.module.requests, etc.)
8. Wait for: **"AIOStreams Add-on enabled"** notification

#### Step 5: Verify Installation

1. Navigate to: **Add-ons → Video add-ons**
2. You should see: **AIOStreams** in the list
3. Right-click and select: **Information**
4. Verify version is current (3.5.4 or later)

✅ **Installation Complete!** Proceed to [Initial Configuration](#initial-configuration)

---

### Method 2: Manual Zip Installation

Install directly from the addon zip file without using the repository.

> **Note**: Manual installation means you won't receive automatic updates. Use repository installation when possible.

#### Step 1: Enable Unknown Sources

1. Open Kodi
2. Navigate to: **Settings → System → Add-ons**
3. Enable: **Unknown sources**

#### Step 2: Download Addon

Download the latest addon zip:
- **URL**: [plugin.video.aiostreams.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/repo/plugin.video.aiostreams/plugin.video.aiostreams-3.5.4.zip)

#### Step 3: Install Addon

1. In Kodi, go to: **Settings → Add-ons**
2. Click: **Install from zip file**
3. Browse to the downloaded `plugin.video.aiostreams-3.5.4.zip`
4. Select the file and wait for installation
5. Dependencies install automatically
6. Wait for: **"Add-on enabled"** notification

#### Step 4: Verify Installation

1. Navigate to: **Add-ons → Video add-ons**
2. Verify **AIOStreams** appears in the list

✅ **Installation Complete!** Proceed to [Initial Configuration](#initial-configuration)

---

## Initial Configuration

After installation, configure the addon to connect to your AIOStreams backend.

### Step 1: Open Addon Settings

1. Navigate to: **Add-ons → Video add-ons → AIOStreams**
2. **Right-click** on AIOStreams
3. Select: **Settings**

### Step 2: Configure AIOStreams Host

**Settings → General → AIOStreams Configuration**

1. **AIOStreams Host URL**:
   - Enter your AIOStreams server address
   - Examples:
     - Self-hosted: `http://192.168.1.100:8080`
     - Self-hosted with domain: `https://aiostreams.yourdomain.com`
     - ElfHosted: `https://your-instance.elfhosted.com`

   > **Important**: Include `http://` or `https://` and the port if needed

2. **Manifest URL**:
   - Leave blank (auto-filled from host)

3. **Request Timeout**:
   - Default: 10 seconds
   - Increase if server is slow: 15-20 seconds

### Step 3: Test Connection

1. Navigate to: **Settings → Advanced → Maintenance**
2. Click: **Test AIOStreams Connection**
3. You should see:
   ```
   ✓ Connection successful!

   Server: https://your-server.com
   Response time: 0.23s
   Catalogs available: 15
   ```

4. If connection fails, see [Troubleshooting](#troubleshooting-connection-issues)

### Step 4: Configure Basic Settings (Optional)

**Settings → General → Playback Settings**

- **Default Behavior**:
  - `show_streams` (default) - Shows all streams for manual selection
  - `play_first` - Auto-plays first available stream

**Settings → General → Quality Settings**

- **Preferred Quality**: Select your preferred quality (any/4k/1080p/720p/480p)
- **Minimum Quality**: Hide streams below this quality
- **Hide Low Quality Streams**: Enable to filter low-quality streams

✅ **Basic Configuration Complete!**

The addon is now functional for browsing and streaming content.

---

## AIOStreams Backend Setup

Ensure your AIOStreams backend is properly configured for optimal addon performance.

### Required AIOStreams Configuration

1. **Stream Scrapers**:
   - Configure at least one scraper in AIOStreams
   - Recommended: Google Drive or GDrive Lite formatters
   - Test scrapers work before using addon

2. **Search Provider**:
   - Configure search endpoint in AIOStreams
   - **Recommended**: AIOMetadata
   - Alternative: Direct TMDb/TVDb integration

3. **Metadata Source**:
   - Configure metadata endpoint in AIOStreams
   - **Recommended**: AIOMetadata
   - Provides rich metadata (posters, fanart, cast, ratings)

4. **Subtitle Scrapers** (Optional):
   - Configure subtitle providers in AIOStreams
   - Automatically integrated when available

### AIOMetadata Integration (Recommended)

[AIOMetadata](https://github.com/cedya77/aiometadata) provides the best metadata and search experience.

#### Setup AIOMetadata:

1. **Deploy AIOMetadata**:
   - Self-host or use ElfHosted
   - Follow AIOMetadata installation guide

2. **Configure in AIOStreams**:
   - Set AIOMetadata URL as search provider
   - Set AIOMetadata URL as metadata source
   - Configure TMDb/TVDb API keys in AIOMetadata

3. **Test Integration**:
   - Search for content in AIOStreams web interface
   - Verify metadata appears correctly

### Testing AIOStreams Backend

Before using the Kodi addon, test your AIOStreams backend:

1. **Open AIOStreams Web Interface**:
   - Navigate to your AIOStreams URL in browser
   - Example: `http://localhost:8080`

2. **Test Search**:
   - Search for popular movie (e.g., "Inception")
   - Verify results appear

3. **Test Scraping**:
   - Click on a movie/show
   - Verify streams are found

4. **Test Playback**:
   - Click a stream link
   - Verify it's a valid video URL

✅ Once backend is working, the Kodi addon will work seamlessly.

---

## Trakt Integration Setup

Trakt integration provides powerful sync features: watchlists, watch history, progress tracking, and recommendations.

### Prerequisites

1. **Trakt Account**: Create free account at [trakt.tv](https://trakt.tv)
2. **Trakt API Application**: Required for OAuth authentication

### Step 1: Create Trakt API Application

1. **Login to Trakt**: [trakt.tv](https://trakt.tv)

2. **Create New Application**:
   - Navigate to: [trakt.tv/oauth/applications/new](https://trakt.tv/oauth/applications/new)

3. **Fill Application Details**:
   ```
   Name: AIOStreams Kodi
   Description: AIOStreams Kodi Addon Integration
   Redirect URI: urn:ietf:wg:oauth:2.0:oob
   Permissions: (Select all the following)
   ☑ /scrobble
   ☑ /sync/collection
   ☑ /sync/history
   ☑ /sync/playback
   ☑ /sync/rating
   ☑ /sync/watchlist
   ☑ /recommendations
   ```

4. **Save Application**

5. **Copy Credentials**:
   - **Client ID**: Long alphanumeric string (copy this)
   - **Client Secret**: Long alphanumeric string (copy this)

   > **Important**: Keep Client Secret secure. Never share publicly.

### Step 2: Configure Addon with Trakt Credentials

1. **Open Addon Settings**:
   - Add-ons → Video add-ons → AIOStreams → Right-click → Settings

2. **Navigate to Trakt Category**:
   - Settings → **Trakt**

3. **Enter Credentials**:
   - **Client ID**: Paste your Trakt Client ID
   - **Client Secret**: Paste your Trakt Client Secret

4. **Save Settings**: Click **OK**

### Step 3: Authorize Trakt

1. **Start Authorization**:
   - Settings → Trakt → Click: **Authorize Trakt**

2. **Authorization Dialog Appears**:
   ```
   Trakt Authorization Required

   1. Visit: https://trakt.tv/activate
   2. Enter code: XXXX-XXXX
   3. Click "Authorize" to complete
   ```

3. **Complete Authorization**:
   - Open browser and visit: [trakt.tv/activate](https://trakt.tv/activate)
   - Enter the code shown in Kodi dialog
   - Click **Continue**
   - Review permissions and click **Authorize**

4. **Return to Kodi**:
   - Click **OK** in the Kodi dialog
   - You should see: **"Trakt authorized successfully"**

### Step 4: Configure Trakt Sync Settings

**Settings → Trakt → Sync Settings**

- **Enable Auto-Sync**: `✓` Enabled (default)
  - Background service syncs every 5 minutes
  - Only syncs changed data (delta sync)

**Settings → Trakt → Trakt Features**

- **Enable Scrobbling**: `✓` Enabled (default)
  - Automatically tracks playback to Trakt
  - Updates watch status and progress

### Step 5: Initial Sync

1. **Navigate to Addon Main Menu**:
   - Add-ons → Video add-ons → AIOStreams

2. **Open Trakt Menu**:
   - Select: **Trakt** folder

3. **First Load Triggers Sync**:
   - Initial sync may take 30-60 seconds
   - Progress dialog shows: "Syncing with Trakt..."
   - Subsequent loads are instant (from database)

### Step 6: Verify Trakt Integration

Test Trakt features are working:

1. **Check Watchlist**:
   - Trakt → Watchlist
   - Should show your Trakt watchlist items

2. **Check Next Up**:
   - Trakt → Next Up
   - Should show next unwatched episodes

3. **Test Context Menu**:
   - Right-click any movie/show
   - Verify "Add to Watchlist" / "Remove from Watchlist" appears
   - Verify "Mark as Watched" / "Mark as Unwatched" appears

✅ **Trakt Integration Complete!**

### Revoking Trakt Authorization

To disconnect Trakt:

1. Settings → Trakt → Click: **Revoke Authorization**
2. Confirmation dialog appears
3. Click **Yes** to revoke
4. All Trakt data remains in local database

---

## TMDBHelper Integration

TMDBHelper provides unified content discovery and playback interface. AIOStreams can integrate as a player.

### Prerequisites

1. **TMDBHelper Installed**: Available from official Kodi repository
2. **AIOStreams Configured**: Backend must be working

### Step 1: Install TMDBHelper

1. **Open Kodi Add-ons**:
   - Settings → Add-ons → Install from repository

2. **Navigate to**:
   - Kodi Add-on repository → Video add-ons

3. **Find and Install**:
   - Select: **TMDbHelper**
   - Click: **Install**
   - Wait for installation to complete

### Step 2: Download AIOStreams Player Configs

Download the pre-configured player files:

- **URL**: [tmdbhelper-players.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/TMDB%20Helper%20Players/tmdbhelper-players.zip)
- Save and extract the zip file

### Step 3: Install Player Configs

#### Option A: Manual Installation

1. **Locate TMDBHelper Players Folder**:

   **Windows**:
   ```
   %APPDATA%\Kodi\userdata\addon_data\plugin.video.themoviedb.helper\players\
   ```

   **Linux**:
   ```
   ~/.kodi/userdata/addon_data/plugin.video.themoviedb.helper/players/
   ```

   **macOS**:
   ```
   ~/Library/Application Support/Kodi/userdata/addon_data/plugin.video.themoviedb.helper/players/
   ```

   **Android**:
   ```
   /sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/plugin.video.themoviedb.helper/players/
   ```

2. **Copy Files**:
   - Extract the downloaded `tmdbhelper-players.zip`
   - Copy both JSON files to the `players/` folder:
     - `aiostreams.direct.json`
     - `aiostreams.select.json`

3. **Restart Kodi**: Required for TMDBHelper to detect new players

#### Option B: File Manager Installation (Kodi)

1. **Access File Manager**:
   - Settings → File manager → Add source

2. **Add Source**:
   - Browse to location of extracted player files
   - Add as source

3. **Copy via Kodi**:
   - Use Kodi's file manager to copy JSON files
   - Destination: TMDBHelper players folder

### Step 4: Verify Player Installation

1. **Open TMDBHelper Settings**:
   - Add-ons → Video add-ons → TMDbHelper → Right-click → Settings

2. **Navigate to Players**:
   - Settings → Players → Manage Players

3. **Check Players List**:
   - You should see:
     - ✓ **AIOStreams** (Priority 200)
     - ✓ **AIOStreams (Source Select)** (Priority 201)

### Player Configurations Explained

#### aiostreams.direct.json (Automatic Playback)

```json
{
  "name": "AIOStreams",
  "priority": 200,
  "play_movie": "plugin://plugin.video.aiostreams/?action=play_first&content_type=movie&imdb_id={imdb}",
  "play_episode": "plugin://plugin.video.aiostreams/?action=play_first&content_type=series&imdb_id={imdb}&season={season}&episode={episode}",
  "is_resolvable": "true",
  "fallback": {
    "play_episode": "aiostreams.select.json play_episode",
    "play_movie": "aiostreams.select.json play_movie"
  }
}
```

**Features:**
- Uses `play_first` endpoint - always direct plays first stream
- Ignores AIOStreams addon's default behavior setting
- Falls back to source selection on playback failure
- **Best for**: Users who want instant playback

#### aiostreams.select.json (Manual Selection)

```json
{
  "name": "AIOStreams (Source Select)",
  "priority": 201,
  "play_movie": "plugin://plugin.video.aiostreams/?action=select_stream&content_type=movie&imdb_id={imdb}",
  "play_episode": "plugin://plugin.video.aiostreams/?action=select_stream&content_type=series&imdb_id={imdb}&season={season}&episode={episode}",
  "is_resolvable": "true"
}
```

**Features:**
- Uses `select_stream` endpoint - shows stream selection dialog
- Displays quality badges and reliability ratings
- Allows manual source selection
- **Best for**: Users who want control over source selection

### Step 5: Test TMDBHelper Integration

1. **Open TMDBHelper**:
   - Add-ons → Video add-ons → TMDbHelper

2. **Browse Content**:
   - Search or browse for a movie/show

3. **Play Content**:
   - Select a movie or episode
   - Choose: **AIOStreams** or **AIOStreams (Source Select)**
   - Content should play via AIOStreams

✅ **TMDBHelper Integration Complete!**

---

## Advanced Configuration

### Stream Quality and Filtering

**Settings → General → Quality Settings**

Fine-tune stream selection based on quality preferences:

- **Preferred Quality**:
  - `any` - No preference, show all
  - `4k` - Prefer 4K/2160p streams
  - `1080p` - Prefer Full HD streams
  - `720p` - Prefer HD streams
  - `480p` - Prefer SD streams

- **Minimum Quality**:
  - Set lowest acceptable quality
  - Hides streams below this threshold
  - Options: 240p, 360p, 480p, 720p, 1080p

- **Hide Low Quality Streams**:
  - Enable to filter out low-quality streams automatically

**How Quality Detection Works:**
- Addon parses stream titles for quality indicators
- Recognizes: 4K, 2160p, UHD, 1080p, FHD, 720p, HD, 480p, SD, 360p, 240p
- Color-coded badges: [4K] [1080p] [720p] [SD]

### Stream Reliability Tracking

**Settings → User Interface**

- **Show Reliability Icons**: Display star ratings on streams
- **Learn Stream Preferences**: Prioritize preferred providers

**How Reliability Tracking Works:**

1. **Success/Failure Tracking**:
   - Addon tracks which streams successfully play
   - Calculates success rate per provider
   - Stores statistics in: `stream_stats.json`

2. **Star Ratings**:
   - ★★★ Excellent (90%+ success)
   - ★★☆ Good (70-89% success)
   - ★☆☆ Fair (50-69% success)
   - ☆☆☆ Poor (<50% success)

3. **Preference Learning**:
   - Remembers which providers you select
   - Prioritizes your preferred providers
   - Stored in: `stream_prefs.json`

4. **Stream Sorting**:
   - 1st: Quality (preferred → highest available)
   - 2nd: Reliability (highest success rate)
   - 3rd: Learned preferences (most frequently selected)

**Maintenance:**
- Clear Statistics: Settings → Advanced → Clear Stream Statistics
- Clear Preferences: Settings → Advanced → Clear Learned Preferences

### UI Enhancements

**Settings → User Interface → Display Options**

Customize visual appearance:

- **Show Progress Bars**: `✓` Enabled
  - Visual indicators for watch progress
  - Shows: [████████░░] 85% (episode) or 8/10 (season)

- **Color Code by Watch Status**: `✓` Enabled
  - Blue: Watched content
  - Gold: In-progress (partially watched)
  - White: Unwatched content

- **Show Quality Badges**: `✓` Enabled
  - Displays quality labels: [4K] [1080p] [720p]
  - Color-coded for easy identification

- **Show Reliability Icons**: `✓` Enabled
  - Displays star ratings: ★★★ ★★☆ ★☆☆
  - Shows provider success rates

### Performance Tuning

**Settings → Advanced → Performance**

Optimize performance based on your setup:

- **Cache Expiry (hours)**: Default 24
  - How long to cache metadata
  - Longer = fewer API calls, less fresh data
  - Shorter = more API calls, fresher data
  - Recommended: 12-48 hours

- **Max Streams to Display**: Default 20
  - Limit number of streams shown
  - Lower = faster selection dialog
  - Higher = more options
  - Recommended: 15-30 streams

- **Stream Test Timeout (sec)**: Default 5
  - Timeout for testing stream availability
  - Increase if streams are slow to respond
  - Decrease for faster selection
  - Recommended: 3-10 seconds

### Debug Logging

**Settings → Advanced → Debug**

- **Enable Debug Logging**: Disabled by default
  - Enables detailed logging for troubleshooting
  - Logs include: API calls, stream parsing, Trakt sync
  - Check logs: Settings → System → Logging → View Log

**When to Enable:**
- Troubleshooting connection issues
- Investigating playback failures
- Reporting bugs to developer

**Viewing Logs:**
1. Settings → System → Logging
2. Enable: Component-specific logging
3. Click: View Log File
4. Search for: `plugin.video.aiostreams`

---

## Keyboard Shortcuts Setup (Optional)

Add keyboard shortcuts for quick actions while browsing content.

### Step 1: Locate Keymap Template

The addon includes a keymap template:
```
plugin.video.aiostreams/keymap.xml.template
```

### Step 2: Copy Keymap File

Copy the template to Kodi's keymaps folder:

**Windows**:
```
Copy from: <addon_path>/keymap.xml.template
Copy to:   %APPDATA%\Kodi\userdata\keymaps\aiostreams.xml
```

**Linux**:
```bash
cp ~/.kodi/addons/plugin.video.aiostreams/keymap.xml.template \
   ~/.kodi/userdata/keymaps/aiostreams.xml
```

**macOS**:
```bash
cp ~/Library/Application\ Support/Kodi/addons/plugin.video.aiostreams/keymap.xml.template \
   ~/Library/Application\ Support/Kodi/userdata/keymaps/aiostreams.xml
```

**Android** (via File Manager):
```
Copy from: /sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/plugin.video.aiostreams/keymap.xml.template
Copy to:   /sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/keymaps/aiostreams.xml
```

### Step 3: Restart Kodi

Restart Kodi for keymaps to take effect.

### Default Keyboard Shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| **Q** | Toggle Watchlist | Add/remove from Trakt watchlist |
| **W** | Mark as Watched | Toggle watched status |
| **I** | Show Info | Display detailed information |
| **S** | Similar Content | Browse related/similar content |
| **A** | Quick Actions | Open quick actions menu |

### Customizing Shortcuts

Edit `aiostreams.xml` to customize shortcuts:

```xml
<keymap>
  <FullscreenVideo>
    <keyboard>
      <q>RunPlugin(plugin://plugin.video.aiostreams/?action=toggle_watchlist)</q>
      <w>RunPlugin(plugin://plugin.video.aiostreams/?action=toggle_watched)</w>
      <!-- Add your custom shortcuts here -->
    </keyboard>
  </FullscreenVideo>
</keymap>
```

---

## Troubleshooting

### Connection Issues

#### Problem: "Unable to connect to AIOStreams"

**Solutions:**

1. **Verify AIOStreams URL**:
   - Check Settings → General → AIOStreams Host URL
   - Ensure URL is correct including protocol (http/https)
   - Test URL in browser - should show AIOStreams interface

2. **Check Network Connectivity**:
   - Ensure Kodi device can reach AIOStreams server
   - Test from browser on same device
   - Verify no firewall blocking connection

3. **Test Connection**:
   - Settings → Advanced → Maintenance → Test AIOStreams Connection
   - Check error message for details

4. **Increase Timeout**:
   - Settings → General → Request Timeout
   - Increase to 15-20 seconds for slow servers

5. **Check AIOStreams Logs**:
   - View AIOStreams backend logs
   - Look for connection errors or crashes

#### Problem: "Connection timeout"

**Solutions:**
- Increase timeout: Settings → General → Request Timeout
- Check AIOStreams server is running
- Verify network latency (ping server)
- Try different network connection

### Trakt Issues

#### Problem: "Trakt authorization failed"

**Solutions:**

1. **Verify Credentials**:
   - Double-check Client ID is correct
   - Double-check Client Secret is correct
   - Ensure no extra spaces when pasting

2. **Check Trakt Application**:
   - Visit: [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications)
   - Verify application exists and is active
   - Verify Redirect URI is: `urn:ietf:wg:oauth:2.0:oob`

3. **Re-authorize**:
   - Settings → Trakt → Revoke Authorization
   - Settings → Trakt → Authorize Trakt
   - Follow authorization flow again

#### Problem: "Trakt lists are empty"

**Solutions:**

1. **Force Sync**:
   - Settings → Advanced → Maintenance → Database Reset
   - Restart addon
   - Open Trakt menu to trigger sync

2. **Check Trakt Account**:
   - Visit [trakt.tv](https://trakt.tv) in browser
   - Verify your watchlist/collection has content
   - Add test items if empty

3. **Check Auto-Sync**:
   - Settings → Trakt → Enable Auto-Sync
   - Ensure it's enabled

#### Problem: "Scrobbling not working"

**Solutions:**

1. **Enable Scrobbling**:
   - Settings → Trakt → Enable Scrobbling
   - Ensure it's enabled

2. **Check Trakt Permissions**:
   - Verify API application has `/scrobble` permission
   - Re-authorize if needed

3. **Test Manually**:
   - Play content for at least 5 minutes
   - Check Trakt website for updated watch history
   - May take a few minutes to appear

### Playback Issues

#### Problem: "No streams found"

**Solutions:**

1. **Check AIOStreams Backend**:
   - Test search/scraping in AIOStreams web interface
   - Verify scrapers are working
   - Check scraper configuration

2. **Check Quality Filters**:
   - Settings → General → Quality Settings
   - Temporarily set Preferred Quality to "any"
   - Disable "Hide Low Quality Streams"

3. **Clear Cache**:
   - Settings → Advanced → Refresh Manifest Cache
   - Restart addon

#### Problem: "Streams fail to play"

**Solutions:**

1. **Try Different Stream**:
   - Use "Show Streams" to see all options
   - Try multiple sources
   - Check reliability ratings

2. **Check Stream URL**:
   - Enable debug logging
   - Check log for stream URL
   - Test URL directly in browser/player

3. **Update Stream Statistics**:
   - Settings → Advanced → Clear Stream Statistics
   - Start fresh with reliability tracking

4. **Check Network**:
   - Some streams may be geo-blocked
   - Try VPN if necessary

#### Problem: "Playback stutters/buffers"

**Solutions:**

1. **Select Lower Quality**:
   - Settings → General → Preferred Quality
   - Choose 720p or 480p instead of 1080p/4K

2. **Check Internet Speed**:
   - Test internet connection speed
   - 4K requires 25+ Mbps
   - 1080p requires 10+ Mbps
   - 720p requires 5+ Mbps

3. **Adjust Cache**:
   - Kodi Settings → Player → Videos
   - Increase buffer size

### TMDBHelper Integration Issues

#### Problem: "AIOStreams not appearing in TMDBHelper"

**Solutions:**

1. **Verify Player Files**:
   - Check files exist in: `addon_data/plugin.video.themoviedb.helper/players/`
   - Files should be: `aiostreams.direct.json` and `aiostreams.select.json`

2. **Restart Kodi**:
   - TMDBHelper only detects players on startup
   - Restart required after adding player files

3. **Check TMDBHelper Settings**:
   - TMDBHelper → Settings → Players → Manage Players
   - Verify AIOStreams players are listed and enabled

#### Problem: "Modal dialog error" when using TMDBHelper

**Solution:**
- This should be fixed in current version (3.5.3+)
- Ensure addon is updated to latest version
- If still occurring, report as bug with details

### Performance Issues

#### Problem: "Addon is slow"

**Solutions:**

1. **Wait for Initial Sync**:
   - First load always slower (building database)
   - Subsequent loads should be instant

2. **Disable Color Coding**:
   - Settings → User Interface → Color Code by Watch Status
   - Disable if Trakt sync is slow

3. **Increase Cache Expiry**:
   - Settings → Advanced → Cache Expiry
   - Increase to 48 hours or more

4. **Reduce Max Streams**:
   - Settings → Advanced → Max Streams to Display
   - Lower to 10-15 for faster dialogs

5. **Clear Database**:
   - Settings → Advanced → Database Reset
   - Fresh start if database corrupted

#### Problem: "High memory usage"

**Solutions:**
- Restart Kodi periodically
- Clear cache: Settings → Advanced → Refresh Manifest Cache
- Reduce Cache Expiry

### General Issues

#### Problem: "Addon won't start"

**Solutions:**

1. **Check Dependencies**:
   - Ensure script.module.requests is installed
   - Check for dependency errors in log

2. **Reinstall Addon**:
   - Uninstall AIOStreams
   - Restart Kodi
   - Reinstall from repository or zip

3. **Check Logs**:
   - View Kodi log file
   - Search for errors related to `plugin.video.aiostreams`

#### Problem: "Settings not saving"

**Solutions:**

1. **Check File Permissions**:
   - Ensure Kodi has write access to addon_data folder
   - Check folder permissions

2. **Check Storage Space**:
   - Ensure device has free storage space

3. **Reinstall Addon**:
   - Note: May lose settings
   - Uninstall and reinstall

---

## Updating the Addon

### Via Repository (Automatic)

If installed via repository, updates are automatic:

1. **Check for Updates**:
   - Kodi checks periodically (default: daily)
   - Updates download and install automatically

2. **Manual Update Check**:
   - Settings → Add-ons → Check for updates

3. **Verify Version**:
   - Add-ons → Video add-ons → AIOStreams
   - Right-click → Information
   - Check version number

### Manual Update

If installed manually:

1. **Download Latest Version**:
   - [plugin.video.aiostreams-3.5.4.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/repo/plugin.video.aiostreams/plugin.video.aiostreams-3.5.4.zip)

2. **Install Over Existing**:
   - Settings → Add-ons → Install from zip file
   - Select new zip file
   - Kodi will upgrade existing installation

3. **Settings Preserved**:
   - All settings are retained during upgrade
   - No need to reconfigure

### Switching from Manual to Repository

To start receiving automatic updates:

1. **Install Repository**:
   - Follow [Method 1: Repository Installation](#method-1-repository-installation-recommended)

2. **Addon Automatically Managed**:
   - No need to uninstall existing addon
   - Repository takes over update management

---

## Additional Resources

### Documentation

- **README.md**: Overview, features, architecture, and quick start
- **FEATURES.md**: Detailed feature guide with examples
- **GitHub Repository**: [github.com/shiggsy365/AIOStreamsKODI](https://github.com/shiggsy365/AIOStreamsKODI)

### Related Projects

- **AIOStreams**: [github.com/Viren070/aiostreams](https://github.com/Viren070/aiostreams)
- **AIOMetadata**: [github.com/cedya77/aiometadata](https://github.com/cedya77/aiometadata)
- **Trakt**: [trakt.tv](https://trakt.tv)
- **TMDBHelper**: Available in Kodi official repository

### Support

- **GitHub Issues**: [Report a bug or request a feature](https://github.com/shiggsy365/AIOStreamsKODI/issues)
- **Kodi Forum**: Community support and discussion

### Contributing

Contributions welcome! Support the developer:

[<img src="https://github.com/shiggsy365/AIOStreamsKODI/blob/main/.github/support_me_on_kofi_red.png?raw=true">](https://ko-fi.com/shiggsy365)

---

## Frequently Asked Questions

### Q: Do I need a Trakt account?

**A**: No, Trakt is optional. The addon works for streaming without Trakt, but you'll miss sync features like watchlists, watch history, and progress tracking.

### Q: Can I use multiple AIOStreams backends?

**A**: No, currently only one backend URL can be configured. You can change it in settings.

### Q: Does this addon host or provide content?

**A**: No, the addon only connects to your AIOStreams backend. You must configure your own backend with scrapers.

### Q: Is this legal?

**A**: The addon itself is legal software. Legality of streamed content depends on your jurisdiction and content sources. Users are responsible for compliance with local laws.

### Q: Why aren't automatic updates working?

**A**: Automatic updates only work if installed via repository. Manual zip installation requires manual updates.

### Q: Can I use this on FireStick/Android TV?

**A**: Yes, works on any device that runs Kodi 19+.

### Q: How do I backup my settings?

**A**: Backup the entire addon_data folder:
- `userdata/addon_data/plugin.video.aiostreams/`
- Includes settings, database, and statistics

### Q: Can I use this with Real-Debrid or Premiumize?

**A**: If your AIOStreams backend is configured with RD/PM scrapers, yes. Configure in AIOStreams, not the addon.

---

**Installation Guide Version**: 3.5.4
**Last Updated**: 2026-01-08
**Addon Version**: 3.5.4 or later
