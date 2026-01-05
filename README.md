# AIOStreams Kodi Addon

A powerful Kodi addon for streaming content from AIOStreams with comprehensive Trakt integration, advanced search capabilities, and smart metadata caching.

## Features

### Core Features
- **AIOStreams Integration**: Browse catalogs, search content, and stream from AIOStreams
- **Trakt Integration**: Full sync with Trakt for watchlists, collections, watch history, and progress tracking
- **Smart Caching**: Disk-based metadata cache reduces API calls and improves performance
- **Advanced Search**: Tabbed search interface with separate Movies/TV Shows/All Results views
- **Metadata, Catalog and Subtitle synchronisation**: Pulls metadata, catalogs and subtitles from AIO manifests
- **TMDbHelper Compatibility**, TMDbHelper Players are saved in the repo

### Trakt Features
- **Next Up**: Smart list of next unwatched episodes from your watched shows
- **Watchlist**: Full access to your Trakt watchlists
- **Progress Tracking**: Automatic scrobbling and progress tracking
- **Context Menus**: Quick actions for adding to watchlist, marking watched, and more

### Performance
- **30-Day Cache**: Metadata cached for 30 days to minimize API requests

### Content Discovery
- **Trailers**: Automatic trailer parsing from metadata with YouTube integration
- **Cast & Crew**: Full cast information with photos
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
Or if you want to add search to a custom menu item, use the below:
```
ActivateWindow(videos, plugin://plugin.video.aiostreams/?action=search&content_type=both&nocache=$INFO[System.Time(ss)],return)
```

## Trakt Setup

1. Navigate to Settings in the addon
2. Select "Authorize Trakt"
3. Visit the provided URL and enter the code
4. Return to Kodi and confirm authorization
5. You will need a trakt api app (available via https://trakt.tv/oauth/applications)

## Widget Support

The addon is optimized for use as a Kodi widget:

- All lists support widget integration
- Fast loading with cached metadata
- Progress indicators and watched status
- Episode-specific thumbnails for continue watching

## Performance Tips

1. **Initial Load**: First load of lists may be slow as cache builds
2. **Subsequent Loads**: Lists load instantly with warm cache
3. **Cache Cleanup**: Cache automatically cleans expired entries (30+ days)
4. **Manual Cache Clear**: Use Settings > Clear Cache if needed


## Credits

- **Developer**: shiggsy365
- **AIOStreams**: Content source and metadata
- **AIOmetadata**: Metadata lists
- **Trakt**: Watch history and recommendations
- **Kodi Community**: Testing and feedback

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Report an issue](https://github.com/shiggsy365/AIOStreamsKODI/issues)

## License

MIT License - See LICENSE file for details
