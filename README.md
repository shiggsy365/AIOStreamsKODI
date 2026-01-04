# AIOStreams Kodi Addon

A comprehensive Kodi addon for streaming movies and TV shows with full Trakt.tv integration.

## Features

### 🎬 Content Discovery
- **Unified Search**: Search both movies and TV shows in one query
- **Movie & TV Show Catalogs**: Browse trending, popular, and genre-specific content
- **AIOStreams Integration**: Direct access to your AIOStreams server content

### 📺 Trakt.tv Integration
- **Continue Watching**: Resume shows where you left off
- **Next Up**: See what episodes to watch next
- **Watchlist**: Sync your Trakt watchlist (Movies & Shows)
- **Collection**: Access your Trakt collection
- **Trending & Popular**: Discover what's trending on Trakt
- **Recommended**: Get personalized recommendations
- **Scrobbling**: Automatic playback tracking
- **Watched Indicators**: Visual markers for watched content at all levels:
  - Movies: Shows if watched in Trakt history
  - Shows: Shows if all episodes are watched
  - Seasons: Shows if entire season is watched
  - Episodes: Shows individual episode watched status

### 🎯 Smart Features
- **Disk-Based Metadata Cache**: 30-day cache for faster loading
- **Genre Filtering**: Filter content by genre (configurable in settings)
- **Context Menus**: Right-click options for:
  - Add to Trakt Watchlist
  - Mark as Watched
  - Browse Show (for episodes in widgets)
  - Play Trailer (when available)

### 🔍 Search Capabilities
- **Unified Search**: One search for both movies and TV shows
  - Returns first 10 results of each type
  - "View All" links for comprehensive results
- **Dedicated Searches**: Separate movie-only or TV-only searches
- **Paginated Results**: "Load More" for large result sets

## Installation

### Prerequisites
1. **Kodi 21 (Omega)** or newer
2. **AIOStreams Server**: You need access to an AIOStreams server
   - Self-hosted or third-party
   - Must have your server URL and credentials

### Install Addon
1. Download `aiostreams-kodi-addon.zip`
2. In Kodi: Settings → Add-ons → Install from zip file
3. Select the downloaded zip file
4. Wait for "AIOStreams Add-on enabled" notification

### Configure AIOStreams
1. Open addon settings
2. Go to "AIOStreams Configuration"
3. Set your **Base URL** (e.g., `https://your-server.com/stremio/YOUR-ID/YOUR-TOKEN`)
4. Test connection

### Configure Trakt (Optional)
1. Open addon settings
2. Go to "Trakt Configuration"
3. Click "Authorize Trakt"
4. Follow on-screen instructions to link your Trakt account
5. Once authorized, all Trakt features will be available

## Usage

### Main Menu
When you open AIOStreams, you'll see:

```
🔍 Search (Movies & TV Shows)
🔍 Search Movies
🔍 Search TV Shows
🎬 Movie Lists
📺 Series Lists
⭐ Trakt Catalogs (if authorized)
```

### Searching
1. Click any search option
2. Type your query in the keyboard dialog
3. Results display with posters and metadata
4. Click any item to:
   - Movies: View available streams
   - TV Shows: Browse seasons → episodes → streams

### Watching Content
1. Navigate to a movie or episode
2. Click to view available streams
3. Select stream quality/source
4. Video starts playing
5. Playback automatically syncs to Trakt (if authorized)

### Using Trakt Lists
**Continue Watching:**
- Shows episodes you're currently watching
- Displays progress percentage
- Right-click: Mark as Watched, Browse Show

**Next Up:**
- Shows next episodes to watch
- Based on your viewing history
- Organized by show

**Watchlist:**
- Items you've saved to watch later
- Synced from Trakt.tv
- Separate lists for Movies & Shows

**Collection:**
- Items you own/collected
- Synced from Trakt.tv

## Settings

### AIOStreams Configuration
- **Base URL**: Your AIOStreams server URL (required)
- **Metadata Cache TTL**: Fixed at 30 days

### Trakt Configuration
- **Authorize Trakt**: Link your Trakt account
- **Revoke Authorization**: Unlink Trakt account
- **Scrobbling**: Enabled by default when authorized

### Filters
- **Genre Filtering**: Enable/disable genre filters
- **Select Genres**: Choose which genres to show/hide

## Content Structure

### Movies
```
Search/Browse → Movie → Stream Selection → Play
```

### TV Shows
```
Search/Browse → Show → Seasons → Episodes → Stream Selection → Play
```

## Metadata

All content includes:
- **Poster**: High-quality poster image
- **Fanart**: Background artwork
- **Plot**: Description/synopsis
- **Rating**: IMDB rating
- **Year**: Release year
- **Runtime**: Duration
- **Genres**: Categories
- **Cast**: Actors list
- **Director**: Director name(s)
- **Writers**: Writer name(s)
- **Clearlogo**: Logo overlay (if available)
- **Trailer**: YouTube trailer link (if available)

## Caching

**Metadata Cache:**
- Location: `userdata/addon_data/plugin.video.aiostreams/cache/`
- Duration: 30 days
- Format: JSON files
- Cleanup: Automatic on addon startup

**Watched Status Cache:**
- In-memory only (session-based)
- Trakt history: Last 1000 items
- Show progress: Full show data
- Refreshes when addon restarts

## Keyboard Shortcuts (in addon)

While browsing:
- **Enter/Select**: Open item
- **Back**: Return to previous screen
- **Context Menu**: Right-click or 'C' key
- **Info**: 'I' key (shows full metadata)

## Troubleshooting

### "No streams found"
- Check your AIOStreams server is running
- Verify Base URL in settings is correct
- Ensure content exists on your server

### "Trakt authorization failed"
- Check your internet connection
- Make sure you completed the authorization process
- Try revoking and re-authorizing

### Metadata not loading
- Clear cache: Delete `userdata/addon_data/plugin.video.aiostreams/cache/`
- Check Base URL is correct
- Restart Kodi

### Watched indicators not showing
- Make sure Trakt is authorized
- Check items are marked watched on Trakt.tv
- Restart addon to refresh cache

### Search not working
- Ensure Base URL is set in settings
- Check AIOStreams server has search enabled
- Try searching for common titles first

## Technical Details

### Requirements
- Kodi 21.0 (Omega) or higher
- Python 3.8+
- Internet connection
- AIOStreams server access

### Dependencies
- script.module.requests (auto-installed)
- Trakt.tv API (optional, for Trakt features)

### API Endpoints Used
- **AIOStreams**: `/catalog/`, `/meta/`, `/stream/`
- **Trakt**: `/sync/`, `/shows/`, `/users/`, `/oauth/`

### Performance
- Metadata cached for 30 days (zero RAM impact)
- Parallel search for movies + TV shows
- Batch API calls where possible
- Progressive loading for large lists

## Privacy

- **AIOStreams**: Connects to your configured server only
- **Trakt**: Only if you authorize it
  - Sends watch history when scrobbling enabled
  - Syncs watchlist/collection bidirectionally
- **No Analytics**: No tracking or telemetry
- **Local Cache**: All cached data stored locally

## Support

For issues or questions:
1. Check Kodi log file for errors
2. Verify all settings are correct
3. Test with simple queries (e.g., "Inception")
4. Ensure AIOStreams server is accessible

## Version History

### v1.5.3 (Current)
- Removed rating filters
- Fixed watched indicators for shows/seasons/episodes
- Uses Trakt progress API for accurate tracking

### v1.5.2
- Fixed back button in search results
- Added Trakt watched indicators

### v1.5.0
- Added unified search (movies + TV shows)
- Parallel search execution
- Color-coded result headers

### v1.4.0
- Complete metadata display (cast, rating, duration)
- Clearlogo support
- Fixed runtime and release date parsing

### v1.3.7
- Disk-based metadata cache (30-day TTL)
- Zero RAM impact caching system

### v1.3.6
- Fixed Continue Watching mark as watched
- Added Browse Show context menu

## License

This addon is provided as-is for personal use with AIOStreams servers.

## Credits

Created by Jon
Built for Kodi 21 (Omega)
Trakt.tv integration via Trakt API
