# AIOStreams Kodi Addon

A powerful Kodi addon for streaming content from AIOStreams with comprehensive Trakt integration, advanced search capabilities, and smart metadata caching.

## Features

### Core Features
- **AIOStreams Integration**: Browse catalogs, search content, and stream from AIOStreams
- **Trakt Integration**: Full sync with Trakt for watchlists, collections, watch history, and progress tracking
- **Smart Caching**: Disk-based metadata cache reduces API calls and improves performance
- **Advanced Search**: Tabbed search interface with separate Movies/TV Shows/All Results views
- **Episode Thumbnails**: Shows episode-specific landscape thumbnails in continue watching lists

### Trakt Features
- **Continue Watching**: Separate lists for TV shows and movies with progress indicators
- **Next Up**: Smart list of next unwatched episodes from your watched shows
- **Watchlist & Collection**: Full access to your Trakt watchlist and collection
- **Trending & Popular**: Browse trending and popular content
- **Progress Tracking**: Automatic scrobbling and progress tracking
- **Context Menus**: Quick actions for adding to watchlist, marking watched, and more

### Performance
- **Fast List Loading**: Lists load instantly with warm cache (previously 25-38 seconds)
- **No Sequential API Calls**: Optimized to use cached data only in list views
- **30-Day Cache**: Metadata cached for 30 days to minimize API requests

### Content Discovery
- **Trailers**: Automatic trailer parsing from metadata with YouTube integration
- **Cast & Crew**: Full cast information with photos
- **Similar Content**: Browse related movies and shows
- **Rich Metadata**: Posters, fanart, logos, ratings, genres, and more

## Requirements

AIOStreams is required for this plugin, with at least one scraper configured, a search provider configured, and a metadata source configured. Subtitle scrapers are optional but preferred.

I recommend setting up AIOMetadata within AIOStreams, and letting AIOMetadata provide the search and metadata catalogs from TMDb and TVDb. I also recommend self hosting both services to avoid rate limiting.

The stream scraper will work best using the following pattern within the formatter:

**Name Template:**
```
{stream.type::=debrid["{service.shortName}"||""]}{stream.type::=usenet["{service.shortName}"||""]}{stream.type::=p2p["P2P"||""]}{stream.type::=http["Web"||""]}{stream.type::=youtube["YT"||""]}{stream.type::=live["Live"||""]}|{stream.resolution::=2160p["4K"||""]}{stream.resolution::=1440p["2K"||""]}{stream.resolution::=1080p["FHD"||""]}{stream.resolution::=720p["HD"||""]}{stream.resolution::=576p["SD"||""]}{stream.resolution::=480p["SD"||""]}{stream.resolution::=360p["SD"||""]}{stream.resolution::=240p["SD"||""]}{stream.resolution::=144p["LQ"||""]}|{stream.size::>0["{stream.size::bytes}"||""]}|{addon.name}|{service.cached::istrue["Cached "||""]}{service.cached::isfalse["Uncached"||""]}
```

**Description Template:**
```
(Leave blank)
```

### Credits
With many thanks to:
- **Cedya77** for AIOMetadata - [https://github.com/cedya77/aiometadata](https://github.com/cedya77/aiometadata)
- **Viren070** for AIOStreams - [https://github.com/Viren070/aiostreams](https://github.com/Viren070/aiostreams)

## Installation

1. Download the latest release ZIP file
2. In Kodi, go to Settings > Add-ons > Install from zip file
3. Select the downloaded ZIP file
4. Wait for installation confirmation

## Custom Search Integration

For Kodi skins that provide a custom search option, use the following URL format:

```
plugin://plugin.video.aiostreams/?action=search&content_type=both&query=
```

### Search Parameters

- `action=search` - Required: Triggers the search function
- `content_type` - Optional: Filter results by type
  - `movie` - Movies only
  - `series` - TV shows only
  - `both` - All results (default)
- `query` - The search term (append to the URL)

### Examples

**Search for movies:**
```
plugin://plugin.video.aiostreams/?action=search&content_type=movie&query=inception
```

**Search for TV shows:**
```
plugin://plugin.video.aiostreams/?action=search&content_type=series&query=breaking bad
```

**Search all content:**
```
plugin://plugin.video.aiostreams/?action=search&content_type=both&query=matrix
```

## Trakt Setup

1. Navigate to Settings in the addon
2. Select "Authorize Trakt"
3. Visit the provided URL and enter the code
4. Return to Kodi and confirm authorization

## Widget Support

The addon is optimized for use as a Kodi widget:

- All lists support widget integration
- Fast loading with cached metadata
- Progress indicators and watched status
- Episode-specific thumbnails for continue watching

### Recommended Widgets

- **Continue Watching - TV**: `plugin://plugin.video.aiostreams/?action=trakt_continue_watching`
- **Continue Watching - Movies**: `plugin://plugin.video.aiostreams/?action=trakt_continue_movies`
- **Next Up**: `plugin://plugin.video.aiostreams/?action=trakt_next_up`
- **Trending Movies**: `plugin://plugin.video.aiostreams/?action=trakt_trending&media_type=movies`
- **Trending Shows**: `plugin://plugin.video.aiostreams/?action=trakt_trending&media_type=shows`

## Context Menu Actions

Right-click on any item for quick actions:

### Continue Watching Lists
- **Remove from Continue Watching**: Clears progress without marking as watched
- **Add to Watchlist**: Add to your Trakt watchlist
- **Mark as Watched**: Mark as watched and remove from continue watching
- **Browse Show**: View all seasons and episodes (TV shows)

### General Content
- **Play Trailer**: Watch trailer on YouTube (when available)
- **Similar to this**: Browse related content
- **Add/Remove Watchlist**: Toggle watchlist status
- **Mark Watched/Unwatched**: Toggle watched status
- **Quick Actions**: Additional content-specific actions

## Performance Tips

1. **Initial Load**: First load of lists may be slow as cache builds
2. **Subsequent Loads**: Lists load instantly with warm cache
3. **Cache Cleanup**: Cache automatically cleans expired entries (30+ days)
4. **Manual Cache Clear**: Use Settings > Clear Cache if needed

## Troubleshooting

### Lists Loading Slowly
- First load builds cache - this is normal
- Subsequent loads should be instant
- If persistently slow, try clearing cache in settings

### Missing Cast Photos
- Cast photos come from cached AIOStreams metadata
- View individual items to populate cache
- Cache persists for 30 days

### Trakt Not Working
- Verify authorization in settings
- Check internet connection
- Re-authorize if needed

## Version History

### v2.3.2 (Latest)
- Major performance improvements (25-38s → <1s list loading)
- Fixed cache to work properly
- Added cast photos to Trakt lists from cached data
- Removed sequential API calls from all list views

### v2.3.1
- Fixed cast display errors
- Fixed "Similar to this" content type detection
- Improved error handling for Trakt cast images

### v2.3.0
- Added tabbed search interface
- Added cast/director search capability
- Enhanced search with better content type filtering

### v2.2.0
- Fixed cast display using proper xbmc.Actor objects
- Improved metadata alignment with AIOStreams format

## Credits

- **Developer**: Jon
- **AIOStreams**: Content source and metadata
- **Trakt**: Watch history and recommendations
- **Kodi Community**: Testing and feedback

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Report an issue](https://github.com/shiggsy365/AIOStreamsKODI/issues)
- Kodi Forums: Community support

## License

MIT License - See LICENSE file for details
