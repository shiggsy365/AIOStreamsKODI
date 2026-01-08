# AIOStreams Kodi Addon

A powerful Kodi addon for streaming content from AIOStreams with comprehensive Trakt integration, intelligent stream selection, and advanced playback features.

## Overview

AIOStreams Kodi Addon is a feature-rich video plugin that integrates [AIOStreams](https://github.com/Viren070/aiostreams) backend with Kodi's media center interface. It provides seamless access to streaming content with advanced features like Trakt synchronization, stream quality filtering, reliability tracking, and TMDBHelper integration for enhanced content discovery.

### What is AIOStreams?

[AIOStreams](https://github.com/Viren070/aiostreams) is a self-hosted streaming aggregator that:
- Scrapes content from multiple sources
- Provides unified search across streaming providers
- Offers metadata integration via TMDb/TVDb
- Supports subtitle scraping
- Can be hosted locally or via services like ElfHosted

This Kodi addon acts as a frontend client to your AIOStreams backend, bringing all that functionality into your Kodi media center.

---

## Architecture

### Plugin Structure

The addon is built as a Kodi Python plugin with the following components:

```
plugin.video.aiostreams/
├── addon.py              # Main plugin entry point & routing
├── service.py            # Background service for Trakt sync
├── resources/
│   ├── lib/
│   │   ├── trakt.py     # Trakt API integration
│   │   ├── database.py  # SQLite database layer
│   │   └── utils.py     # Helper functions
│   ├── settings.xml     # User configuration schema
│   └── language/        # Localization strings
└── addon.xml            # Plugin metadata & dependencies
```

### Core Systems

#### 1. **Action Routing System**
The addon uses an action-based routing system that maps URL parameters to functions:

```python
ACTION_REGISTRY = {
    'play_first': lambda p: play_first(),      # Auto-play first stream
    'select_stream': lambda p: select_stream(),  # Show stream selection
    'show_streams': lambda p: show_streams(),    # Browse all streams
    'search': lambda p: search(),                # Content search
    'trakt_*': lambda p: trakt_handlers()        # Trakt operations
}
```

**Key Endpoints:**
- `play_first` - Always direct plays the first available stream (ignores user settings)
- `select_stream` - Shows a dialog to select from available streams
- `show_streams` - Displays all streams with full metadata
- `play` - Respects user's default_behavior setting (play_first or show_streams)

#### 2. **Trakt Integration**
Complete bidirectional sync with Trakt.tv:

- **OAuth 2.0 Authentication**: Secure token-based authentication
- **Delta Sync**: Only syncs changed data since last update (90%+ API call reduction)
- **Background Service**: Automatic sync every 5 minutes via `service.py`
- **Database Caching**: All Trakt data stored locally in SQLite for instant access
- **Scrobbling**: Automatic watch progress tracking and playback status updates

**Synced Data:**
- Watchlist (movies & shows)
- Collection (owned content)
- Watch history (per episode/movie)
- Playback progress (resume points)
- Hidden items (excluded from recommendations)

#### 3. **Stream Management**
Intelligent stream selection and tracking:

- **Quality Detection**: Automatic parsing of resolution indicators (4K, 1080p, 720p, etc.)
- **Reliability Tracking**: Success/failure tracking for each stream provider
- **Preference Learning**: Learns which providers you prefer and prioritizes them
- **Fallback Handling**: Automatically tries next stream if one fails
- **Statistics Database**: JSON-based storage of stream success rates

#### 4. **Database Layer**
SQLite database for local caching and performance:

```sql
Tables:
- trakt_movies_watchlist
- trakt_movies_watched
- trakt_movies_collected
- trakt_shows_watchlist
- trakt_episodes_watched
- trakt_episodes_collected
- playback_progress
- hidden_items
- metadata_cache
```

Benefits:
- Instant list loading (no API calls)
- Reduced network dependency
- Persistent across Kodi restarts
- Efficient delta sync support

#### 5. **TMDBHelper Integration**
Seamless integration with TMDBHelper for enhanced content discovery:

The addon provides two TMDBHelper player configurations:

**aiostreams.direct.json** (Priority 200):
- Uses `play_first` endpoint for direct playback
- Fallback to source selection on failure
- Best for users who want instant playback

**aiostreams.select.json** (Priority 201):
- Uses `select_stream` endpoint for manual selection
- Shows all available streams with quality/reliability info
- Best for users who want control over source selection

**Resolver State Management:**
- Cancels Kodi's modal resolver state immediately to prevent dialog conflicts
- Uses `xbmcplugin.setResolvedUrl(HANDLE, False, ...)` at function start
- Allows progress dialogs and selection dialogs to display properly

---

## Key Features

### Content Access
- **Browse Catalogs**: Access all AIOStreams catalogs (Movies, TV Shows, Popular, Trending, etc.)
- **Advanced Search**: Tabbed search interface with separate Movies/TV Shows/All Results views
- **Metadata Integration**: Rich metadata from TMDb/TVDb including posters, fanart, cast, ratings
- **Subtitle Support**: Automatic subtitle scraping via AIOStreams backend
- **Trailer Playback**: YouTube trailer integration for content preview

### Trakt Features
- **Full Sync**: Watchlist, collections, watch history, and progress tracking
- **Next Up**: Smart list showing next unwatched episodes from your watched shows
- **Continue Watching**: Resume partially watched content with progress indicators
- **Dynamic Context Menus**: Right-click actions that adapt based on watch status
- **Auto-Scrobbling**: Automatic playback tracking to Trakt
- **Delta Sync**: Intelligent sync only downloads changed data (90%+ API reduction)

### Stream Management
- **Quality Filtering**: Set preferred and minimum quality levels (4K, 1080p, 720p, etc.)
- **Reliability Tracking**: Star ratings show success rates for each provider
- **Preference Learning**: Addon learns which providers you prefer and sorts accordingly
- **Smart Sorting**: Streams sorted by quality → reliability → learned preferences
- **Quality Badges**: Color-coded quality indicators ([4K], [1080p], [720p])
- **Fallback Options**: Automatic retry with next stream on playback failure

### UI Enhancements
- **Progress Bars**: Visual indicators showing watch progress for episodes/seasons
- **Color Coding**: Blue (watched), Gold (in-progress), White (unwatched)
- **Loading Screens**: Progress dialogs during stream scraping
- **Episode Thumbnails**: Show-specific thumbnails for continue watching
- **Keyboard Shortcuts**: Optional keymaps for quick actions (Q, W, I, S, A)

### Performance
- **SQLite Database**: Local caching reduces API calls by 95%+
- **Stream Pre-loading**: Caches first 3 Next Up items with 15-minute TTL
- **Metadata Caching**: Configurable cache expiry (default 24 hours)
- **Throttled Sync**: 5-minute throttle prevents excessive Trakt API calls
- **Widget Support**: Optimized for use as Kodi home screen widgets

---

## Requirements

### AIOStreams Backend
You must have a running AIOStreams instance configured with:

1. **At least one scraper configured**: For finding streams
2. **Search provider configured**: For content search (recommend AIOMetadata)
3. **Metadata source configured**: For rich content info (recommend AIOMetadata via TMDb/TVDb)
4. **Subtitle scraper** (optional but recommended): For subtitle integration

### Recommended Setup
- **AIOMetadata**: Provides TMDb/TVDb metadata and search catalogs
  - GitHub: [cedya77/aiometadata](https://github.com/cedya77/aiometadata)
  - Configure as both search and metadata source in AIOStreams

- **Custom Formatter**: Configure your AIOStreams custom formatter with the following format for optimal display:

  **Name field:**
  ```
  {stream.resolution::exists["RESOLUTION: {stream.resolution}"||""]}
  {service.name::exists["SERVICE: {service.name}"||""]}
  {addon.name::exists["ADDON: {addon.name}"||""]}
  {stream.size::>0["SIZE: {stream.size::bytes}"||""]}
  {stream.proxied::istrue["PROXIED: YES"||""]}{stream.proxied::isfalse["PROXIED: NO"||""]}
  {service.cached::istrue["CACHED: YES"||""]}{service.cached::isfalse["CACHED:NO"||""]}
  {stream.library::istrue["IN LIBRARY: YES"||""]}{stream.library::isfalse["IN LIBRARY: NO"||""]}
  {stream.duration::>0["DURATION: {stream.duration::time} "||""]}
  {stream.quality::exists["VIDEO: {stream.quality}"||""]} | {stream.visualTags} | {stream.encode}
  {stream.audioTags::exists["AUDIO: {stream.audioTags::join(' | ')} | {stream.audioChannels}"||""]}{stream.languages::exists[" | {stream.languages::join(' / ')}"||""]}
  {stream.indexer::exists["INDEXER: {stream.indexer} "||""]}{stream.seeders::exists["| {stream.seeders} Seeders"||""]}{stream.age::exists[" | {stream.age} Old"||""]}
  {stream.filename::exists["FILENAME: {stream.filename}"||""]}
  ```

  **Description field:** Leave blank

  This format provides structured stream information with:
  - Resolution, Service, and Addon at the top
  - Organized rows for Size, Proxied status, Library status, and Duration
  - Video quality and Indexer information
  - Audio details and Cache status
  - Complete filename for reference

- **Hosting**: Self-host both AIOStreams and AIOMetadata to avoid rate limiting

### Kodi Requirements
- **Kodi 19+ (Matrix/Nexus/Omega)**: Python 3 addon support
- **script.module.requests**: HTTP library (auto-installed)
- **resource.fonts.noto-emoji** (optional): Enhanced emoji rendering

### Optional Integrations
- **Trakt Account**: For sync features (create at [trakt.tv](https://trakt.tv))
- **Trakt API Application**: Required for OAuth (create at [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications))
- **TMDBHelper**: For enhanced content discovery and unified playback interface

---

## Installation

**See [INSTALLATION.md](INSTALLATION.md) for complete installation guide.**

### Quick Start

1. **Install Repository**:
   - Download [repository.aiostreams.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/repository.aiostreams.zip)
   - Kodi → Settings → Add-ons → Install from zip file

2. **Install Addon**:
   - Settings → Add-ons → Install from repository → AIOStreams Repository → Video add-ons → AIOStreams

3. **Configure**:
   - Add-ons → Video add-ons → AIOStreams → Right-click → Settings
   - Set AIOStreams Host URL
   - (Optional) Configure Trakt integration

---

## TMDBHelper Integration

The addon includes pre-configured TMDBHelper players for seamless integration.

### Installing TMDBHelper Players

1. **Install TMDBHelper** (if not already installed):
   - Available from official Kodi repository

2. **Install Player Configs**:
   - Download [tmdbhelper-players.zip](https://github.com/shiggsy365/AIOStreamsKODI/raw/main/TMDB%20Helper%20Players/tmdbhelper-players.zip)
   - Extract to: `<kodi_userdata>/addon_data/plugin.video.themoviedb.helper/players/`

3. **Included Configurations**:

   **aiostreams.direct.json** - Automatic playback
   ```json
   {
     "name": "AIOStreams",
     "priority": 200,
     "play_movie": "plugin://plugin.video.aiostreams/?action=play_first&...",
     "play_episode": "plugin://plugin.video.aiostreams/?action=play_first&...",
     "is_resolvable": "true",
     "fallback": {
       "play_episode": "aiostreams.select.json play_episode",
       "play_movie": "aiostreams.select.json play_movie"
     }
   }
   ```
   - Always direct plays first stream (ignores addon default behavior setting)
   - Falls back to source selection on failure
   - Best for "just play it" experience

   **aiostreams.select.json** - Manual selection
   ```json
   {
     "name": "AIOStreams (Source Select)",
     "priority": 201,
     "play_movie": "plugin://plugin.video.aiostreams/?action=select_stream&...",
     "play_episode": "plugin://plugin.video.aiostreams/?action=select_stream&..."
   }
   ```
   - Shows stream selection dialog
   - Displays quality badges and reliability ratings
   - Best for users who want source control

### Usage with TMDBHelper

Once installed, AIOStreams will appear as a player option in TMDBHelper:
1. Browse content in TMDBHelper
2. Select a movie or episode
3. Choose "AIOStreams" or "AIOStreams (Source Select)" as player
4. Content plays via AIOStreams backend

---

## Configuration

### AIOStreams Backend

**Settings → General → AIOStreams Configuration**

- **AIOStreams Host URL**: Your AIOStreams server address
  - Example: `https://aiostreams.elfhosted.com`
  - Or: `http://localhost:8080` for local installations
- **Manifest URL**: Auto-filled from host (no manual configuration needed)
- **Request Timeout**: Connection timeout in seconds (default: 10)

### Playback Behavior

**Settings → General → Playback Settings**

- **Default Behavior**:
  - `show_streams` (default): Show all streams for manual selection
  - `play_first`: Auto-play first available stream

- **Fallback on Stream Failure**:
  - `show_streams` (default): Show all streams if first fails
  - `play_next`: Automatically try next stream

### Quality Settings

**Settings → General → Quality Settings**

- **Preferred Quality**: `any` | `4k` | `1080p` | `720p` | `480p` (default: any)
- **Minimum Quality**: `240p` | `360p` | `480p` | `720p` | `1080p` (default: 480p)
- **Hide Low Quality Streams**: Filter out streams below minimum quality

### Resume & Progress

**Settings → General → Resume & Progress**

- **Auto Resume Playback**: Resume from last position (default: enabled)
- **Mark Watched at %**: Percentage to mark as watched (default: 90%)

### Trakt Configuration

**Settings → Trakt**

See [INSTALLATION.md - Trakt Setup](INSTALLATION.md#trakt-integration-setup) for complete OAuth configuration guide.

- **Client ID**: Your Trakt API application Client ID
- **Client Secret**: Your Trakt API application Client Secret
- **Authorize Trakt**: Start OAuth flow
- **Enable Auto-Sync**: Background service syncs every 5 minutes (default: enabled)
- **Enable Scrobbling**: Automatic playback tracking (default: enabled)

### User Interface

**Settings → User Interface**

- **Show Progress Bars**: Visual progress indicators (default: enabled)
- **Color Code by Watch Status**: Color code items by watch state (default: enabled)
- **Show Quality Badges**: Display quality labels on streams (default: enabled)
- **Show Reliability Icons**: Display star ratings on streams (default: enabled)
- **Learn Stream Preferences**: Prioritize preferred providers (default: enabled)

### Advanced Settings

**Settings → Advanced**

**Performance:**
- **Cache Expiry (hours)**: Metadata cache duration (default: 24)
- **Max Streams to Display**: Limit streams shown (default: 20)
- **Stream Test Timeout (sec)**: Timeout for testing streams (default: 5)

**Debug:**
- **Enable Debug Logging**: Detailed logging for troubleshooting

**Maintenance:**
- **Refresh Manifest Cache**: Force reload of AIOStreams catalogs
- **Database Reset**: Clear all Trakt sync data
- **Show Database Info**: View database statistics
- **Clear Stream Statistics**: Reset reliability tracking
- **Clear Learned Preferences**: Reset provider preferences
- **Test AIOStreams Connection**: Diagnostic connection test

---

## Usage

### Main Menu
Access from: **Add-ons → Video add-ons → AIOStreams**

- **Catalogs**: Browse all AIOStreams catalogs
- **Search**: Search movies and TV shows
- **Trakt → Next Up**: Next unwatched episodes from watched shows
- **Trakt → Continue Watching**: Resume partially watched content
- **Trakt → Watchlist**: Your Trakt watchlist
- **Trakt → Collection**: Your collected content

### Context Menu Actions
Right-click any movie/show:
- **Play / Show Streams**: Playback options
- **Add to Watchlist** / **Remove from Watchlist**: Watchlist management
- **Mark as Watched** / **Mark as Unwatched**: Watch status
- **Play Trailer**: Watch YouTube trailer
- **Similar to this...**: Browse related content
- **Quick Actions**: Fast access menu

### Keyboard Shortcuts (Optional)
After installing keymap (see [INSTALLATION.md](INSTALLATION.md)):
- **Q**: Toggle watchlist
- **W**: Mark as watched
- **I**: Show info
- **S**: Similar content
- **A**: Quick actions menu

### Custom Search Integration
For Kodi skins with custom search:
```
plugin://plugin.video.aiostreams/?action=search&content_type=both&query=
```

Or for menu items:
```
ActivateWindow(videos, plugin://plugin.video.aiostreams/?action=search&content_type=both&nocache=$INFO[System.Time(ss)],return)
```

---

## Widget Support

The addon is optimized for use as Kodi home screen widgets:

- All lists support widget integration
- Fast loading with cached metadata
- Progress indicators and watched status visible
- Episode-specific thumbnails for continue watching
- Pre-loads streams for first 3 Next Up items (15-minute cache)

**Recommended Widget Lists:**
- **Next Up**: Shows next unwatched episodes
- **Continue Watching**: Resume in-progress content
- **Trending**: Popular content
- **Watchlist**: Your Trakt watchlist

---

## Performance Tips

1. **Initial Load**: First load may be slow while database builds
2. **Subsequent Loads**: Lists load instantly from cache
3. **Stream Pre-loading**: First 3 Next Up items pre-cached for instant playback
4. **Disable Color Coding**: If Trakt sync is slow, disable color coding
5. **Increase Cache Expiry**: Longer cache = fewer API calls
6. **Reduce Max Streams**: Lower limit = faster stream selection

---

## Credits

**Developer**: [shiggsy365](https://github.com/shiggsy365)

**Powered By:**
- **[AIOStreams](https://github.com/Viren070/aiostreams)** by Viren070 - Content source and streaming backend
- **[AIOMetadata](https://github.com/cedya77/aiometadata)** by Cedya77 - Metadata and catalog provider
- **[Trakt.tv](https://trakt.tv)** - Watch history and recommendations
- **Kodi Community** - Testing and feedback

---

## Support

**Issue Reporting:**
- GitHub Issues: [Report an issue](https://github.com/shiggsy365/AIOStreamsKODI/issues)

**Documentation:**
- [INSTALLATION.md](INSTALLATION.md) - Complete installation guide
- [FEATURES.md](plugin.video.aiostreams/FEATURES.md) - Detailed feature documentation

**Contribution:**

[<img src="https://github.com/shiggsy365/AIOStreamsKODI/blob/main/.github/support_me_on_kofi_red.png?raw=true">](https://ko-fi.com/shiggsy365)

---

## License

MIT License - See [LICENSE](LICENSE) for details

---

**Version**: 3.5.4
**Last Updated**: 2026-01-08
