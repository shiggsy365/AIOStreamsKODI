# Installation Guide

Complete installation and configuration guide for AIOStreams Kodi Addon.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Initial Configuration](#initial-configuration)
- [Settings Deep Dive](#settings-deep-dive)
- [TMDBHelper Integration](#tmdbhelper-integration)
- [Trakt Integration Setup](#trakt-integration-setup)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required: AIOStreams Backend

You **must** have a running AIOStreams instance before installing this addon.

#### Option 1: ElfHosted (Easiest)
- Sign up at [ElfHosted](https://elfhosted.com)
- Subscribe to AIOStreams service
- Note your instance URL (e.g., `https://aiostreams-yourusername.elfhosted.com`)

#### Option 2: Self-Hosted (Recommended for Power Users)
1. Follow [AIOStreams installation guide](https://github.com/Viren070/aiostreams)
2. Configure at least one scraper (torrent indexer or debrid service)
3. Configure search provider (recommend AIOMetadata)
4. Configure metadata source (recommend AIOMetadata)

### Required: AIOMetadata (Highly Recommended)

For the best experience, configure [AIOMetadata](https://github.com/cedya77/aiometadata) as your search and metadata provider:

1. Install AIOMetadata following its documentation
2. In AIOStreams settings, set AIOMetadata as:
   - Search provider
   - Metadata source

This provides rich TMDb/TVDb metadata and comprehensive search catalogs.

### Kodi Requirements

- **Kodi 19 or higher** (Matrix, Nexus, Omega)
  - Python 3 addon support required
- **script.module.requests** (automatically installed as dependency)

### Optional Components

- **Trakt Account** - For watch history sync features ([trakt.tv](https://trakt.tv))
- **TMDBHelper** - For enhanced content discovery ([official Kodi repo](https://kodi.wiki/view/Add-on:The_Movie_Database_Helper))
- **resource.fonts.noto-emoji** - For better emoji rendering in stream info

---

## Installation Methods

### Method 1: From Repository (Recommended)

**Step 1: Add Repository Source**

1. In Kodi, go to **Settings** → **File manager** → **Add source**
2. Click **<None>** to add a new source
3. Enter repository URL: `https://shiggsy365.github.io/AIOStreamsKODI/`
4. Give it a name: `AIOStreams Repo`
5. Click **OK**

**Step 2: Install Repository**

1. Go to **Settings** → **Add-ons**
2. Select **Install from zip file**
3. Navigate to **AIOStreams Repo**
4. Select `repository.aiostreams-x.x.x.zip`
5. Wait for "Add-on installed" notification

**Step 3: Install Addon**

1. Select **Install from repository**
2. Choose **AIOStreams Repository**
3. Navigate to **Video add-ons**
4. Select **AIOStreams**
5. Click **Install**
6. Confirm dependency installation (script.module.requests)
7. Wait for "Add-on enabled" notification

### Method 2: From Zip File (Manual)

1. Download latest release from [Releases](https://github.com/shiggsy365/AIOStreamsKODI/releases)
2. In Kodi: **Settings** → **Add-ons** → **Install from zip file**
3. Navigate to download location
4. Select `plugin.video.aiostreams-x.x.x.zip`
5. Confirm dependency installation
6. Wait for installation notification

---

## Initial Configuration

### Quick Setup (Minimum Configuration)

**Step 1: Open Settings**

1. Navigate to **Add-ons** → **Video add-ons**
2. Find **AIOStreams**
3. Right-click (or press C) → **Settings**

**Step 2: Configure AIOStreams Backend**

1. Go to **General** category
2. Under **AIOStreams Configuration**:
   - **AIOStreams Host URL**: Enter your AIOStreams server URL
     - ElfHosted: `https://aiostreams-yourusername.elfhosted.com`
     - Self-hosted: `http://your-server-ip:8080` or your domain
   - **Manifest URL**: Automatically filled (leave as is)
   - **Request Timeout**: Leave at 10 seconds (increase if slow network)

**Step 3: Test Connection**

1. Go to **Advanced** category
2. Under **Maintenance**, click **Test AIOStreams Connection**
3. Verify successful connection message

**Step 4: Start Using**

You can now access the addon from **Add-ons** → **Video add-ons** → **AIOStreams**!

---

## Settings Deep Dive

### General Settings

#### AIOStreams Configuration

**AIOStreams Host URL**
- Your AIOStreams server address
- Must include protocol (`http://` or `https://`)
- Examples:
  - `https://aiostreams.elfhosted.com`
  - `http://192.168.1.100:8080`
  - `https://my-aiostreams.domain.com`

**Configure AIOStreams (Open Browser)**
- Opens your AIOStreams web interface in default browser
- Useful for configuring scrapers, metadata sources, etc.

**Manifest URL**
- Auto-filled from host URL
- Shows the manifest endpoint being used
- Don't modify unless you know what you're doing

**Request Timeout**
- Default: 10 seconds
- How long to wait for AIOStreams responses
- Increase if you have slow network or distant server
- Range: 5-30 seconds recommended

#### Playback Settings

**Default Behavior**
- `show_streams` (default): Always show stream selection dialog
- `play_first`: Auto-play first available stream

**When to use each:**
- `show_streams`: Best for users who want control over quality/source
- `play_first`: Best for "just play it" experience, faster playback start

**Fallback on Stream Failure**
- Only visible when `Default Behavior` is `play_first`
- `show_streams` (default): Show all streams if first fails
- `play_next`: Automatically try next stream without showing dialog

#### Quality Settings

**Preferred Quality**
- `any` (default): No preference, shows all qualities
- `4k`: Prefer 4K/2160p streams
- `1080p`: Prefer Full HD streams
- `720p`: Prefer HD streams
- `480p`: Prefer SD streams

Note: This is a preference, not a filter. Higher quality streams are still shown.

**Minimum Quality**
- Default: `480p`
- Options: `240p` | `360p` | `480p` | `720p` | `1080p`
- Streams below this quality won't be shown

**Hide Low Quality Streams**
- Default: Disabled
- When enabled, filters out streams below minimum quality
- When disabled, low quality streams shown but marked/sorted lower

#### Subtitle Settings

**Filter Subtitle Languages**
- Comma-separated 3-letter language codes
- Example: `eng,spa,fre` for English, Spanish, French
- Leave blank to show all languages
- Uses ISO 639-3 codes

#### Resume & Progress

**Auto Resume Playback**
- Default: Enabled
- Automatically resume from last watched position
- Requires Trakt integration for cross-device sync
- Local resume points stored even without Trakt

**Mark Watched at %**
- Default: 90%
- When to automatically mark content as watched
- Range: 50-100%
- Example: At 90%, anything beyond 90% is marked watched

#### Autoplay Next Episode

**Enable Autoplay Next Episode**
- Default: Disabled
- Shows countdown dialog near end of TV episodes
- Only works for TV shows (not movies)

**Shows under 15 min (seconds before end)**
- Default: 20 seconds
- When to show autoplay dialog for short episodes
- Example: 12-minute episode shows dialog at 11:40

**Shows under 30 min (seconds before end)**
- Default: 30 seconds
- For typical sitcom-length episodes
- Example: 22-minute episode shows dialog at 21:30

**Shows under 45 min (seconds before end)**
- Default: 45 seconds
- For typical drama-length episodes
- Example: 42-minute episode shows dialog at 41:15

**Shows over 45 min (seconds before end)**
- Default: 60 seconds
- For feature-length episodes
- Example: 60-minute episode shows dialog at 59:00

**How Autoplay Works:**
1. At (configured time - 10s), streams start scraping in background
2. At configured time, dialog appears with episode thumbnail and title
3. User can click "Play Now", "Stop Watching", or wait 10 seconds
4. After countdown, next episode auto-plays

---

### Trakt Settings

See [Trakt Integration Setup](#trakt-integration-setup) for complete OAuth setup.

**Client ID / Client Secret**
- Your Trakt API application credentials
- Required for OAuth authentication

**Authorize Trakt**
- Starts OAuth flow to link your Trakt account
- Opens authorization page in browser

**Revoke Authorization**
- Disconnects Trakt account
- Clears all tokens and synced data

**Enable Auto-Sync (Background Service)**
- Default: Enabled
- Syncs watchlist, collections, history every 5 minutes
- Uses delta sync (only changed data)

**Enable Scrobbling**
- Default: Enabled
- Automatically tracks what you're watching
- Updates Trakt in real-time during playback

---

### User Interface Settings

**Show Progress Bars**
- Default: Enabled
- Visual progress bars for episodes and seasons
- Format: `[████████░░] 85%`

**Color Code by Watch Status**
- Default: Enabled
- Blue: Watched
- Gold: In progress
- White: Unwatched

**Show Quality Badges**
- Default: Enabled
- Displays quality labels on streams: [4K], [1080p], [720p]

**Show Reliability Icons**
- Default: Enabled
- Star ratings based on success rate:
  - ★★★★★: 90%+ success
  - ★★★★☆: 70-89% success
  - ★★★☆☆: 50-69% success
  - ★★☆☆☆: 30-49% success
  - ★☆☆☆☆: <30% success

**Learn Stream Preferences**
- Default: Enabled
- Tracks which providers you select most often
- Prioritizes preferred providers in future selections
- Reset via Advanced → Clear Learned Preferences

---

### Advanced Settings

#### Performance

**Cache Expiry (hours)**
- Default: 24 hours
- How long to cache metadata before refreshing
- Lower = more up-to-date, more API calls
- Higher = better performance, possibly stale data
- Range: 1-168 hours (1 week)

**Max Streams to Display**
- Default: 20
- Limits number of streams shown in selection
- Lower = faster loading
- Higher = more options
- Range: 5-100

**Stream Test Timeout (sec)**
- Default: 5 seconds
- Timeout for testing stream availability
- Increase if streams frequently fail to load
- Range: 3-15 seconds

#### Debug

**Enable Debug Logging**
- Default: Disabled
- Enables verbose logging for troubleshooting
- Logs written to Kodi log file
- Useful for reporting issues

#### Maintenance

**Refresh Manifest Cache**
- Forces reload of AIOStreams catalog list
- Use if catalogs aren't showing up
- Clears and rebuilds catalog cache

**Database Reset**
- **Warning**: Deletes all Trakt sync data
- Requires re-sync from Trakt
- Use if database is corrupted

**Show Database Info**
- Displays statistics:
  - Total movies/shows synced
  - Total episodes watched
  - Database file size
  - Last sync time

**Clear Stream Statistics**
- Resets reliability tracking for all providers
- Stars return to neutral state
- Use if statistics seem inaccurate

**Clear Learned Preferences**
- Resets provider preference learning
- Streams return to default sorting
- Use if you want to start fresh

**Test AIOStreams Connection**
- Diagnostic tool to verify backend connectivity
- Shows connection status and latency
- Reports any configuration errors

---

### Filter Settings

**Enable Rating Filters**
- Master switch for content rating filters
- When disabled, all rating checkboxes are inactive

**Hide Ratings**
Individual checkboxes for each rating:

**Movies:**
- G, PG, PG-13, R, NC-17

**TV Shows:**
- TV-Y, TV-Y7, TV-G, TV-PG, TV-14, TV-MA

When enabled, content with selected ratings will be hidden from lists.

---

## TMDBHelper Integration

TMDBHelper provides a unified interface for discovering and playing content across multiple addons.

### Installing TMDBHelper

**Step 1: Install TMDBHelper**
1. Go to **Settings** → **Add-ons**
2. Select **Install from repository**
3. Choose **Kodi Add-on repository**
4. Navigate to **Information providers**
5. Select **The Movie Database Helper**
6. Click **Install**

**Step 2: Download Player Configurations**
1. Download [tmdbhelper-players.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/TMDB%20Helper%20Players/tmdbhelper-players.zip)
2. Extract the zip file

**Step 3: Install Player Configs**
1. Locate your Kodi userdata folder:
   - **Windows**: `%APPDATA%\Kodi\userdata\`
   - **Mac**: `~/Library/Application Support/Kodi/userdata/`
   - **Linux**: `~/.kodi/userdata/`
   - **Android**: `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/`
2. Navigate to `addon_data/plugin.video.themoviedb.helper/players/`
   - Create the `players` folder if it doesn't exist
3. Copy the extracted JSON files to this folder

**Step 4: Configure TMDBHelper**
1. Open TMDBHelper settings
2. Go to **Players** tab
3. Enable **AIOStreams** and **AIOStreams (Source Select)**
4. Set priority order (higher = tried first)

### Player Configurations

**aiostreams.direct.json** (Priority 200)
- **Direct Playback**: Auto-plays first available stream
- **Fallback**: Shows source selection if first stream fails
- **Best for**: "Just play it" experience

**aiostreams.select.json** (Priority 201)
- **Manual Selection**: Always shows stream selection dialog
- **Quality Info**: Displays quality badges and reliability ratings
- **Best for**: Users who want source control

### Using TMDBHelper with AIOStreams

1. Open TMDBHelper
2. Browse or search for content
3. Select a movie or episode
4. Choose **Play** from context menu
5. TMDBHelper will use AIOStreams as configured
6. Content plays via your AIOStreams backend

---

## Trakt Integration Setup

Complete guide to setting up Trakt.tv integration.

### Step 1: Create Trakt Account

1. Go to [trakt.tv](https://trakt.tv)
2. Sign up for free account
3. Verify email address

### Step 2: Create Trakt API Application

1. Go to [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications)
2. Click **New Application**
3. Fill in application details:
   - **Name**: `Kodi AIOStreams` (or any name you prefer)
   - **Description**: `AIOStreams Kodi Addon`
   - **Redirect URI**: `urn:ietf:wg:oauth:2.0:oob`
   - **Permissions**: Check all boxes (if available)
4. Click **Save App**
5. Note your **Client ID** and **Client Secret**

### Step 3: Configure Addon

1. Open AIOStreams addon settings
2. Go to **Trakt** category
3. Enter **Client ID** from Step 2
4. Enter **Client Secret** from Step 2
5. Click **Authorize Trakt**

### Step 4: Complete OAuth Flow

1. A browser window will open with Trakt authorization page
2. Review permissions requested
3. Click **Authorize**
4. You'll see an authorization code
5. **Important**: Leave this page open
6. Return to Kodi
7. The addon will automatically detect authorization
8. Wait for "Trakt authorized successfully" notification

### Step 5: Initial Sync

1. First sync will download all your Trakt data
2. This may take a few minutes depending on library size
3. Progress shown via notification
4. Subsequent syncs use delta sync (much faster)

### Trakt Features

**Automatic Sync** (Background Service)
- Runs every 5 minutes
- Only syncs changed data (delta sync)
- Minimal API usage

**Scrobbling**
- Automatic playback tracking
- Updates watch progress in real-time
- Marks content as watched at configured percentage

**Synced Data**
- Watchlist (movies and shows)
- Collection (owned content)
- Watch history (per episode/movie)
- Playback progress (resume points)
- Hidden items (excluded from recommendations)

**Lists Available in Addon**
- Next Up (smart next episode list)
- Continue Watching (resume in-progress content)
- Watchlist
- Collection

---

## Keyboard Shortcuts

Optional keyboard shortcuts for quick actions.

### Installing Keymap

**Step 1: Create Keymap File**

1. Locate Kodi userdata folder (see TMDBHelper section)
2. Navigate to `keymaps/` folder
   - Create folder if it doesn't exist
3. Create file named `aiostreams.xml`

**Step 2: Add Keymap Content**

Copy this content to `aiostreams.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<keymap>
  <global>
    <keyboard>
      <!-- Q = Toggle Watchlist -->
      <q>RunScript(special://home/addons/plugin.video.aiostreams/addon.py,action=trakt_toggle_watchlist)</q>

      <!-- W = Mark as Watched -->
      <w>RunScript(special://home/addons/plugin.video.aiostreams/addon.py,action=trakt_mark_watched)</w>

      <!-- I = Show Info -->
      <i>Action(Info)</i>

      <!-- S = Similar Content -->
      <s>RunScript(special://home/addons/plugin.video.aiostreams/addon.py,action=show_similar)</s>

      <!-- A = Quick Actions Menu -->
      <a>RunScript(special://home/addons/plugin.video.aiostreams/addon.py,action=quick_actions)</a>
    </keyboard>
  </global>
</keymap>
```

**Step 3: Reload Keymaps**

1. Restart Kodi, or
2. Go to **Settings** → **System** → **Input** → **Reload keymaps**

### Available Shortcuts

- **Q**: Toggle Watchlist (add/remove current item)
- **W**: Mark as Watched/Unwatched
- **I**: Show detailed info
- **S**: Browse similar content
- **A**: Open quick actions menu

---

## Troubleshooting

### Connection Issues

**Problem**: "Cannot connect to AIOStreams"

Solutions:
1. Verify AIOStreams host URL is correct
2. Ensure AIOStreams is running and accessible
3. Check firewall settings
4. Try increasing request timeout in settings
5. Use **Test AIOStreams Connection** in Advanced settings

**Problem**: "Manifest not found"

Solutions:
1. Use **Refresh Manifest Cache** in Advanced settings
2. Verify AIOStreams has catalogs configured
3. Check AIOStreams logs for errors

### Stream Issues

**Problem**: "No streams found"

Solutions:
1. Verify scrapers are configured in AIOStreams
2. Check if content is available in your region
3. Try searching for different content
4. Check AIOStreams web interface directly

**Problem**: "Stream fails to play"

Solutions:
1. Try next stream in list
2. Enable debug logging to see detailed error
3. Check if stream URL is still valid
4. Verify debrid service is working (if using)

### Trakt Issues

**Problem**: "Trakt authorization failed"

Solutions:
1. Verify Client ID and Secret are correct
2. Ensure redirect URI is `urn:ietf:wg:oauth:2.0:oob`
3. Check Trakt application is approved
4. Try revoking and re-authorizing

**Problem**: "Sync not updating"

Solutions:
1. Verify auto-sync is enabled in settings
2. Check background service is running
3. Use **Database Reset** and re-sync (last resort)
4. Check Trakt website to verify data exists

### Performance Issues

**Problem**: "Addon is slow"

Solutions:
1. Increase cache expiry time
2. Disable color coding temporarily
3. Reduce max streams to display
4. Clear database and re-sync
5. Check network connection speed

**Problem**: "Lists take long to load"

Solutions:
1. Wait for initial sync to complete
2. Subsequent loads use cached data (instant)
3. Increase cache expiry to reduce refreshes

---

## Getting Help

**Issue Reporting**
- GitHub Issues: [Report a problem](https://github.com/shiggsy365/AIOStreamsKODI/issues)
- Include:
  - Kodi version
  - Addon version
  - Debug log (enable debug logging first)
  - Steps to reproduce

**Documentation**
- [README.md](README.md) - Overview and features
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical details
- [FEATURES.md](plugin.video.aiostreams/FEATURES.md) - Feature documentation

---

### Acknowledgments

This addon is powered by:

- **[AIOStreams](https://github.com/Viren070/aiostreams)** by [Viren070](https://github.com/Viren070) - Streaming aggregation backend
- **[AIOMetadata](https://github.com/cedya77/aiometadata)** by [Cedya77](https://github.com/cedya77) - Metadata and catalog provider

Special thanks to the Kodi community for testing and feedback!

**Support the ecosystem:**

[<img src="https://github.com/shiggsy365/AIOStreamsKODI/blob/main/.github/support_me_on_kofi_red.png?raw=true">](https://ko-fi.com/shiggsy365)
