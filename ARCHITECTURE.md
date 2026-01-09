# Architecture & Technical Documentation

Technical deep dive into the AIOStreams Kodi Addon architecture, integration with AIOStreams and AIOMetadata, and custom template configuration.

---

## Table of Contents

- [Plugin Architecture](#plugin-architecture)
- [Core Systems](#core-systems)
- [AIOStreams Backend](#aiostreams-backend)
- [AIOMetadata Integration](#aiometadata-integration)
- [Custom Templates](#custom-templates)
- [Database Layer](#database-layer)
- [Stream Management](#stream-management)

---

## Plugin Architecture

### Overview

The addon is built as a Kodi Python 3 plugin with a modular architecture designed for performance, maintainability, and extensibility.

### Directory Structure

```
plugin.video.aiostreams/
├── addon.py              # Main entry point & routing logic (~3800 lines)
├── service.py            # Background service for Trakt sync
├── addon.xml             # Plugin manifest & dependencies
├── resources/
│   ├── settings.xml      # User configuration schema
│   ├── lib/
│   │   ├── globals.py    # Singleton global state manager
│   │   ├── router.py     # Action registry system
│   │   ├── monitor.py    # Playback monitoring & autoplay
│   │   ├── streams.py    # Stream quality & reliability management
│   │   ├── ui_helpers.py # UI formatting & colors
│   │   ├── cache.py      # Caching system
│   │   ├── network.py    # HTTP requests
│   │   ├── trakt.py      # Trakt API integration
│   │   ├── filters.py    # Content filtering
│   │   ├── autoplay.py   # Autoplay next episode logic
│   │   ├── providers/    # Stream provider implementations
│   │   │   ├── aiostreams.py
│   │   │   └── base.py
│   │   ├── database/     # Local database for Trakt sync
│   │   │   └── trakt_sync/
│   │   └── gui/          # Custom dialogs & windows
│   │       └── windows/
│   │           ├── multiline_source_select.py
│   │           └── autoplay_next.py
│   └── skins/            # Kodi skin XML files
│       └── Default/1080i/
│           ├── aiostreams-source-select.xml
│           └── aiostreams-autoplay-next.xml
```

### Entry Points

#### Main Plugin (`addon.py`)

The primary entry point for all plugin operations:

```python
# URL format:
plugin://plugin.video.aiostreams/?action=<action>&param1=value1&...

# Main routing function
def router(params):
    """Dispatch actions to registered handlers"""
    action = params.get('action', 'main_menu')
    handler = ACTION_REGISTRY.get(action)
    if handler:
        handler(params)
```

#### Background Service (`service.py`)

Runs continuously in the background for:
- Automatic Trakt sync every 5 minutes
- Background task queue processing
- Stream prefetching

```python
# Starts on Kodi login
# Runs until Kodi shutdown
# Monitors for abort requests
```

---

## Core Systems

### 1. Action Routing System

The addon uses an action-based routing system that maps URL parameters to handler functions:

```python
ACTION_REGISTRY = {
    # Playback actions
    'play': play,                   # Respects user's default behavior setting
    'play_first': play_first,       # Always auto-plays first stream
    'select_stream': select_stream, # Always shows selection dialog
    'show_streams': show_streams,   # Browse all streams with metadata

    # Content browsing
    'search': search,
    'show_catalog': show_catalog,
    'show_seasons': show_seasons,
    'show_episodes': show_episodes,

    # Trakt actions
    'trakt_next_up': trakt_next_up,
    'trakt_continue_watching': trakt_continue_watching,
    'trakt_watchlist': trakt_watchlist,
    'trakt_collection': trakt_collection,
    'trakt_toggle_watchlist': trakt_toggle_watchlist,
    'trakt_mark_watched': trakt_mark_watched,

    # Utility actions
    'show_similar': show_similar,
    'play_trailer': play_trailer,
    'quick_actions': quick_actions,
}
```

**Key Playback Endpoints:**

- **`play`** - Respects user's `default_behavior` setting (play_first or show_streams)
- **`play_first`** - Always direct plays first stream, ignores user setting (used by TMDBHelper)
- **`select_stream`** - Always shows selection dialog (used by TMDBHelper fallback)
- **`show_streams`** - Displays all streams with full metadata browsing

### 2. Trakt Integration

Complete bidirectional sync with Trakt.tv using OAuth 2.0 and delta sync:

**OAuth Flow:**
```python
1. User enters Client ID/Secret in settings
2. Addon generates OAuth URL and opens browser
3. User authorizes on Trakt website
4. Addon polls for authorization code
5. Exchanges code for access/refresh tokens
6. Stores tokens securely in settings
```

**Delta Sync Algorithm:**
```python
def sync_trakt_data():
    """Only sync changed data since last update"""

    # Get last sync timestamp from database
    last_sync = db.get_last_sync_time()

    # Request only items added/changed since last sync
    new_watchlist = trakt.get_watchlist(since=last_sync)
    new_history = trakt.get_history(since=last_sync)

    # Update database with changes only
    db.update_watchlist(new_watchlist)
    db.update_history(new_history)

    # Store new sync timestamp
    db.set_last_sync_time(now())
```

**Benefits:**
- **90%+ API call reduction** compared to full sync
- Fast subsequent syncs (seconds vs minutes)
- Respects Trakt API rate limits
- Minimal bandwidth usage

**Synced Data:**
- Watchlist (movies & shows)
- Collection (owned content)
- Watch history (per episode/movie)
- Playback progress (resume points)
- Hidden items (excluded from recommendations)

**Real-time Scrobbling:**
```python
def onPlayBackStarted():
    trakt.scrobble('start', media_type, imdb_id, progress=0)

def onPlayBackPaused():
    trakt.scrobble('pause', media_type, imdb_id, progress)

def onPlayBackEnded():
    trakt.scrobble('stop', media_type, imdb_id, progress=100)
```

### 3. Stream Management

Intelligent stream selection and tracking system:

**Quality Detection:**
```python
QUALITY_PATTERNS = {
    '4k': ['4k', '2160p', 'uhd'],
    '1080p': ['1080p', 'fhd', 'fullhd'],
    '720p': ['720p', 'hd'],
    '480p': ['480p', 'sd'],
    '360p': ['360p'],
    '240p': ['240p']
}

def detect_quality(stream_name):
    """Parse quality from stream name"""
    name_lower = stream_name.lower()
    for quality, patterns in QUALITY_PATTERNS.items():
        if any(p in name_lower for p in patterns):
            return quality
    return 'unknown'
```

**Reliability Tracking:**
```python
# Stored in addon_data/stream_stats.json
{
    "torrentio_realdebrid": {
        "success": 45,
        "failure": 5,
        "last_used": "2026-01-09T10:30:00"
    }
}

def get_reliability_stars(provider):
    """Convert success rate to star rating"""
    stats = load_stats(provider)
    rate = stats['success'] / (stats['success'] + stats['failure'])

    if rate >= 0.90: return "★★★★★"
    if rate >= 0.70: return "★★★★☆"
    if rate >= 0.50: return "★★★☆☆"
    if rate >= 0.30: return "★★☆☆☆"
    return "★☆☆☆☆"
```

**Preference Learning:**
```python
# Stored in addon_data/stream_prefs.json
{
    "torrentio_realdebrid": 15,  # Selected 15 times
    "orionoid": 8,               # Selected 8 times
    "jackett": 2                 # Selected 2 times
}

def sort_streams(streams):
    """Sort by quality → reliability → learned preference"""
    return sorted(streams, key=lambda s: (
        -QUALITY_ORDER[s['quality']],    # Higher quality first
        -s['reliability'],                # More reliable first
        -get_preference_count(s['provider'])  # Preferred provider first
    ))
```

### 4. Database Layer

SQLite database for local caching and performance:

**Schema:**
```sql
-- Trakt movies
CREATE TABLE trakt_movies_watchlist (
    imdb_id TEXT PRIMARY KEY,
    title TEXT,
    year INTEGER,
    added_at TEXT
);

CREATE TABLE trakt_movies_watched (
    imdb_id TEXT PRIMARY KEY,
    last_watched_at TEXT,
    plays INTEGER
);

-- Trakt shows and episodes
CREATE TABLE trakt_shows_watchlist (
    imdb_id TEXT PRIMARY KEY,
    title TEXT,
    year INTEGER,
    added_at TEXT
);

CREATE TABLE episodes (
    id INTEGER PRIMARY KEY,
    show_trakt_id INTEGER,
    season INTEGER,
    episode INTEGER,
    title TEXT,
    watched INTEGER,
    last_watched_at TEXT
);

-- Playback progress
CREATE TABLE playback_progress (
    imdb_id TEXT PRIMARY KEY,
    season INTEGER,
    episode INTEGER,
    progress REAL,
    updated_at TEXT
);

-- Metadata cache
CREATE TABLE metadata_cache (
    cache_key TEXT PRIMARY KEY,
    data TEXT,
    expires_at TEXT
);
```

**Performance Benefits:**
- **Instant list loading** - No API calls for cached data
- **95%+ API call reduction** - Only fetch when cache expired
- **Offline capability** - Browse watchlist without internet
- **Cross-session persistence** - Data survives Kodi restarts

### 5. TMDBHelper Integration

Seamless integration with TMDBHelper for enhanced content discovery:

**Player Configurations:**

```json
// aiostreams.direct.json (Priority 200)
{
    "name": "AIOStreams",
    "priority": 200,
    "play_movie": "plugin://plugin.video.aiostreams/?action=play_first&content_type=movie&imdb_id=$INFO[imdb_id]",
    "play_episode": "plugin://plugin.video.aiostreams/?action=play_first&content_type=series&imdb_id=$INFO[imdb_id]&season=$INFO[season]&episode=$INFO[episode]",
    "is_resolvable": "true",
    "fallback": {
        "play_episode": "aiostreams.select.json play_episode",
        "play_movie": "aiostreams.select.json play_movie"
    }
}

// aiostreams.select.json (Priority 201)
{
    "name": "AIOStreams (Source Select)",
    "priority": 201,
    "play_movie": "plugin://plugin.video.aiostreams/?action=select_stream&content_type=movie&imdb_id=$INFO[imdb_id]",
    "play_episode": "plugin://plugin.video.aiostreams/?action=select_stream&content_type=series&imdb_id=$INFO[imdb_id]&season=$INFO[season]&episode=$INFO[episode]"
}
```

**Resolver State Management:**

```python
def play_first():
    """Cancel Kodi's resolver immediately to prevent dialog conflicts"""
    # Cancel modal resolver state
    xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())

    # Now safe to show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create('Scraping streams...')

    # Fetch and play stream
    streams = get_streams(content_type, media_id)
    play_stream(streams[0])
```

### 6. Autoplay Next Episode

Intelligent autoplay system for seamless binge-watching:

**Monitoring Flow:**
```python
1. Episode starts playing
2. AIOStreamsPlayer.onPlayBackStarted() triggered
3. AutoplayManager checks if:
   - Is TV show (not movie)
   - Autoplay is enabled in settings
   - Has next episode available
4. Monitor thread starts tracking playback time

5. At (configured_time - 10s) before end:
   - Background thread scrapes next episode streams
   - Fetches next episode metadata (title, thumbnail)

6. At configured_time before end:
   - Dialog appears at bottom left of screen
   - Shows episode thumbnail and title
   - Displays "Play Now" and "Stop Watching" buttons
   - 10-second countdown begins

7. User can:
   - Click "Play Now" - Immediately start next episode
   - Click "Stop Watching" - Cancel autoplay
   - Wait 10 seconds - Auto-play next episode

8. If auto-playing:
   - Current episode stops
   - Next episode starts playing with pre-scraped streams
```

**Timing Configuration:**
```python
def get_timing_config(duration_minutes):
    """Get autoplay timing based on episode length"""

    if duration_minutes < 15:
        return settings.get('autoplay_under_15', 20)  # Short episodes
    elif duration_minutes < 30:
        return settings.get('autoplay_under_30', 30)  # Sitcoms
    elif duration_minutes < 45:
        return settings.get('autoplay_under_45', 45)  # Dramas
    else:
        return settings.get('autoplay_over_45', 60)   # Feature-length
```

---

## AIOStreams Backend

### What is AIOStreams?

[AIOStreams](https://github.com/Viren070/aiostreams) is a self-hosted streaming aggregator that provides a unified API for:

- **Stream scraping** from multiple sources (torrent indexers, debrid services)
- **Metadata integration** via TMDb/TVDb or custom providers
- **Subtitle scraping** from various subtitle databases
- **Catalog management** for browsing popular/trending content
- **Search functionality** across all configured sources

### How This Addon Uses AIOStreams

The addon acts as a Kodi frontend client for your AIOStreams instance:

```python
# Example API calls

# Get available catalogs
GET https://aiostreams.example.com/manifest.json

# Search for content
GET https://aiostreams.example.com/catalog/movie/search.json?q=inception

# Get streams for content
GET https://aiostreams.example.com/stream/movie/tt1375666.json

# Get metadata
GET https://aiostreams.example.com/meta/movie/tt1375666.json

# Get subtitles
GET https://aiostreams.example.com/subtitles/movie/tt1375666.json
```

### Required AIOStreams Configuration

For this addon to work, your AIOStreams instance must have:

1. **At least one scraper configured**:
   - Torrent indexers (Jackett, Prowlarr, etc.)
   - Debrid services (Real-Debrid, AllDebrid, Premiumize, etc.)
   - Direct scrapers (Torrentio, Orionoid, etc.)

2. **Search provider configured**:
   - Recommended: AIOMetadata (see next section)
   - Alternative: Built-in TMDb search

3. **Metadata source configured**:
   - Recommended: AIOMetadata
   - Alternative: Direct TMDb/TVDb API

4. **Optional: Subtitle scraper**:
   - OpenSubtitles
   - Subscene
   - Other subtitle databases

---

## AIOMetadata Integration

### What is AIOMetadata?

[AIOMetadata](https://github.com/cedya77/aiometadata) is a metadata provider that integrates with AIOStreams to provide:

- **Rich TMDb/TVDb metadata** (posters, fanart, cast, ratings, descriptions)
- **Search catalogs** for movies and TV shows
- **Trending/popular catalogs**
- **Genre filtering**
- **Multi-language support**

### Why Use AIOMetadata?

**Benefits over direct TMDb API:**

1. **Catalog Support**: Provides browse catalogs (Popular, Trending, etc.)
2. **Caching**: Built-in caching reduces API calls
3. **Rate Limit Protection**: Handles TMDb rate limits gracefully
4. **Enhanced Metadata**: Combines data from multiple sources
5. **Self-Hosted**: No reliance on third-party services

### Setting Up AIOMetadata

**Step 1: Install AIOMetadata**

Follow the [AIOMetadata installation guide](https://github.com/cedya77/aiometadata) to deploy your own instance.

**Step 2: Configure in AIOStreams**

In your AIOStreams `config.json`:

```json
{
    "searchProvider": {
        "type": "aiometadata",
        "url": "https://aiometadata.example.com"
    },
    "metadataProvider": {
        "type": "aiometadata",
        "url": "https://aiometadata.example.com"
    }
}
```

**Step 3: Verify in Addon**

1. Open addon and go to **Catalogs**
2. You should see catalogs like:
   - Popular Movies
   - Trending Movies
   - Popular TV Shows
   - Trending TV Shows
   - Genre-based catalogs

---

## Custom Templates

### Stream Formatter Templates

AIOStreams allows customizing how stream information is displayed using template formatters.

### Recommended Template Configuration

For optimal display in this addon, configure your AIOStreams custom formatter with:

#### Name Field Template

```
{stream.resolution::exists["RESOLUTION: {stream.resolution}"||""]}
{service.name::exists["SERVICE: {service.name}"||""]}
{addon.name::exists["ADDON: {addon.name}"||""]}
{stream.size::>0["SIZE: {stream.size::bytes}"||""]}
{stream.proxied::istrue["PROXIED: YES"||""]}{stream.proxied::isfalse["PROXIED: NO"||""]}
{service.cached::istrue["CACHED: YES"||""]}{service.cached::isfalse["CACHED: NO"||""]}
{stream.library::istrue["IN LIBRARY: YES"||""]}{stream.library::isfalse["IN LIBRARY: NO"||""]}
{stream.duration::>0["DURATION: {stream.duration::time}"||""]}
{stream.quality::exists["VIDEO: {stream.quality}"||""]} | {stream.visualTags} | {stream.encode}
{stream.audioTags::exists["AUDIO: {stream.audioTags::join(' | ')} | {stream.audioChannels}"||""]}{stream.languages::exists[" | {stream.languages::join(' / ')}"||""]}
{stream.indexer::exists["INDEXER: {stream.indexer}"||""]}{stream.seeders::exists[" | {stream.seeders} Seeders"||""]}{stream.age::exists[" | {stream.age} Old"||""]}
{stream.filename::exists["FILENAME: {stream.filename}"||""]}
```

#### Description Field Template

Leave blank or add custom description:

```
{stream.description::exists["{stream.description}"||""]}
```

### How Templates Work

The custom stream selection dialog (`multiline_source_select.py`) parses the formatted name field into structured fields:

```python
def _parse_stream_fields(text):
    """Parse AIOStreams formatted text into fields"""

    fields = {
        'resolution': '',  # 2160p, 1080p, 720p, etc.
        'service': '',     # Real-Debrid, AllDebrid, etc.
        'addon': '',       # Torrentio, Jackett, etc.
        'size': '',        # 62.5 GB
        'proxied': '',     # YES/NO
        'cached': '',      # YES/NO
        'in_library': '',  # YES/NO
        'duration': '',    # 2h:32m:0s
        'video': '',       # BluRay | DV | HEVC
        'audio': '',       # Atmos | TrueHD | 7.1 | English
        'indexer': '',     # RARBG | 125 Seeders | 10d Old
        'filename': ''     # Full filename
    }

    # Parse each line looking for "KEY: value" format
    for line in text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            # Map to field names
            ...

    return fields
```

These fields are then displayed in the custom XML skin with proper formatting and layout.

### Template Placeholders

Below are placeholders for custom template documentation. **These sections will be expanded in future updates:**

#### [PLACEHOLDER] Advanced Template Syntax

*Documentation coming soon for:*
- Conditional expressions
- Formatting functions
- Nested templates
- Custom functions
- Array operations

#### [PLACEHOLDER] Creating Custom Formatters

*Documentation coming soon for:*
- Step-by-step formatter creation
- Testing formatters
- Debugging template syntax
- Common patterns and examples

#### [PLACEHOLDER] Template Performance

*Documentation coming soon for:*
- Template caching
- Performance optimization
- Best practices
- Avoiding common pitfalls

---

## Database Layer

### Storage Locations

**Database Files:**
```
<kodi_userdata>/addon_data/plugin.video.aiostreams/
├── trakt_sync.db         # Trakt sync data
├── stream_stats.json     # Reliability tracking
├── stream_prefs.json     # Learned preferences
└── cache/                # Metadata cache files
```

### Database Operations

**Common Queries:**

```python
# Get next unwatched episode for each show
def get_next_up_episodes():
    """Pure SQL calculation - no API calls"""

    query = """
        WITH max_watched AS (
            SELECT show_trakt_id,
                   MAX(season) as max_season,
                   MAX(episode) as max_episode
            FROM episodes
            WHERE watched = 1 AND season > 0
            GROUP BY show_trakt_id
        )
        SELECT e.* FROM episodes e
        JOIN max_watched m ON e.show_trakt_id = m.show_trakt_id
        WHERE e.watched = 0
          AND (e.season > m.max_season
               OR (e.season = m.max_season AND e.episode = m.max_episode + 1))
        ORDER BY e.show_trakt_id, e.season, e.episode
    """

    return db.execute(query).fetchall()
```

### Cache Management

**Metadata Caching:**

```python
def get_cached_meta(content_type, meta_id, ttl_seconds):
    """Get metadata from cache if not expired"""

    cache_key = f"{content_type}:{meta_id}"

    # Check cache
    cached = db.execute(
        "SELECT data FROM metadata_cache WHERE cache_key = ? AND expires_at > ?",
        (cache_key, now())
    ).fetchone()

    if cached:
        return json.loads(cached['data'])

    # Cache miss - fetch from API
    data = fetch_from_api(content_type, meta_id)

    # Store in cache
    expires_at = now() + timedelta(seconds=ttl_seconds)
    db.execute(
        "INSERT OR REPLACE INTO metadata_cache VALUES (?, ?, ?)",
        (cache_key, json.dumps(data), expires_at)
    )

    return data
```

---

## Stream Management

### Quality Detection Algorithm

```python
QUALITY_ORDER = {
    '4k': 4,
    '1080p': 3,
    '720p': 2,
    '480p': 1,
    'unknown': 0
}

def detect_quality(stream_name):
    """Extract quality from stream name using patterns"""

    # Normalize
    name = stream_name.lower()

    # Check patterns in priority order
    if any(p in name for p in ['4k', '2160p', 'uhd']):
        return '4k'
    if any(p in name for p in ['1080p', 'fhd', 'fullhd']):
        return '1080p'
    if any(p in name for p in ['720p', 'hd']):
        return '720p'
    if any(p in name for p in ['480p', 'sd']):
        return '480p'

    return 'unknown'
```

### Reliability Tracking

```python
class StreamManager:
    """Manages stream statistics and reliability"""

    def record_success(self, provider):
        """Increment success counter"""
        stats = self.load_stats()
        stats.setdefault(provider, {'success': 0, 'failure': 0})
        stats[provider]['success'] += 1
        stats[provider]['last_used'] = datetime.now().isoformat()
        self.save_stats(stats)

    def record_failure(self, provider):
        """Increment failure counter"""
        stats = self.load_stats()
        stats.setdefault(provider, {'success': 0, 'failure': 0})
        stats[provider]['failure'] += 1
        self.save_stats(stats)

    def get_success_rate(self, provider):
        """Calculate success rate percentage"""
        stats = self.load_stats().get(provider, {})
        total = stats.get('success', 0) + stats.get('failure', 0)
        if total == 0:
            return 0.5  # Neutral for untested providers
        return stats.get('success', 0) / total
```

### Stream Sorting

```python
def sort_streams_by_preference(streams):
    """Multi-criteria sorting: quality → reliability → preference"""

    def sort_key(stream):
        # Extract quality
        quality = detect_quality(stream['name'])
        quality_score = QUALITY_ORDER.get(quality, 0)

        # Get reliability
        provider = stream.get('provider', '')
        reliability = stream_manager.get_success_rate(provider)

        # Get learned preference
        preference = stream_manager.get_preference_count(provider)

        # Return tuple for sorting (higher = better)
        return (
            -quality_score,   # Negative for descending
            -reliability,     # Negative for descending
            -preference       # Negative for descending
        )

    return sorted(streams, key=sort_key)
```

---

## Performance Optimization

### Caching Strategy

**Multi-layer caching:**

1. **In-memory cache** - Fastest, cleared on restart
2. **Database cache** - Persistent, configurable TTL
3. **Stream prefetch** - Pre-loads next 3 episodes

```python
# In-memory cache (globals.py)
class GlobalState:
    def __init__(self):
        self._memory_cache = {}

    def get_cached(self, key, ttl=300):
        """Get from memory cache with TTL"""
        if key in self._memory_cache:
            data, timestamp = self._memory_cache[key]
            if time.time() - timestamp < ttl:
                return data
        return None

# Database cache (cache.py)
def get_cached_meta(content_type, meta_id, ttl_seconds):
    """Get from database cache"""
    # See Cache Management section above
    ...

# Stream prefetch (stream_prefetch.py)
def prefetch_next_up_streams():
    """Pre-load streams for first 3 Next Up episodes"""
    next_episodes = get_next_up_episodes()[:3]
    for episode in next_episodes:
        get_streams_async(episode)  # Background fetch
```

### Widget Optimization

**Fast loading for Kodi widgets:**

```python
def is_widget_context():
    """Detect if being called from widget"""
    return xbmc.getCondVisibility('Window.IsActive(home)')

def show_episodes(show_id):
    """Optimized for widget display"""

    if is_widget_context():
        # Widget mode: fast loading, minimal API calls
        episodes = db.get_cached_episodes(show_id)
        add_episodes_to_list(episodes, cache_to_disk=True)
    else:
        # Full mode: fetch fresh data, full metadata
        episodes = fetch_episodes_with_metadata(show_id)
        add_episodes_to_list(episodes)
```

---

### Acknowledgments

This addon is powered by:

- **[AIOStreams](https://github.com/Viren070/aiostreams)** by [Viren070](https://github.com/Viren070) - The streaming aggregation backend that makes this all possible
- **[AIOMetadata](https://github.com/cedya77/aiometadata)** by [Cedya77](https://github.com/cedya77) - Metadata and catalog provider for rich content information

Special thanks to the Kodi community for testing and feedback!

**Support the ecosystem:**

[<img src="https://github.com/shiggsy365/AIOStreamsKODI/blob/main/.github/support_me_on_kofi_red.png?raw=true">](https://ko-fi.com/shiggsy365)
