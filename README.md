# AIOStreams Kodi Addon

A powerful Kodi addon for streaming content from AIOStreams with comprehensive Trakt integration, SQLite database, advanced search capabilities, and smart metadata caching.

## Features

### Core Features
- **AIOStreams Integration**: Browse catalogs, search content, and stream from AIOStreams
- **Trakt Integration**: Full sync with Trakt for watchlists, collections, watch history, and progress tracking
- **SQLite Database**: Custom database reduces API calls and improves performance
- **Advanced Search**: Tabbed search interface with separate Movies/TV Shows/All Results views
- **Metadata, Catalog and Subtitle synchronisation**: Pulls metadata, catalogs and subtitles from AIO manifests
- **TMDbHelper Compatibility**, TMDbHelper Players are saved in the repo, I suggest editing after installing to have default option as direct play, and fallback as scrape streams.

### Trakt Features
- **Next Up**: Smart list of next unwatched episodes from your watched shows
- **Watchlist**: Full access to your Trakt watchlists
- **Progress Tracking**: Automatic scrobbling and progress tracking
- **Context Menus**: Quick actions for adding to watchlist, marking watched, and more

### Performance
- **SQLite Database**: Caches all watching and watchlist shows for better next up performance and faster loading of catalogs.

### Content Discovery
- **Trailers**: Automatic trailer parsing from metadata with YouTube integration
- **Cast & Crew**: Full cast information with photos
- **Rich Metadata**: Posters, fanart, logos, ratings, genres, and more

## Requirements
AIOStreams is required for this plugin, with at least one scraper configured, a search provider configured, and a metadata source configured. Subtitle scrapers are optional but preferred.

I recommend setting up AIOMetadata within AIOStreams, and letting AIOMetadata provide the search and metadata catalogs from TMDb and TVDb. I also recommend self hosting both services to avoid rate limiting.

The stream scraper will work best using the Google Drive or GDrive Lite custom formatters in AIOStreams

### Credits
With many thanks to:
- **Cedya77** for AIOMetadata - [https://github.com/cedya77/aiometadata](https://github.com/cedya77/aiometadata)
- **Viren070** for AIOStreams - [https://github.com/Viren070/aiostreams](https://github.com/Viren070/aiostreams)

## Installation
(https://github.com/shiggsy365/AIOStreamsKODI/blob/main/INSTALLATION.md)

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

1. **Initial Load**: First load of lists may be slow as database builds
2. **Subsequent Loads**: Lists load instantly with warm cache, and pre-loads stream results for the first 3 next up items with a 15min TTL


## Credits

- **Developer**: shiggsy365
- **AIOStreams**: Content source and metadata
- **AIOmetadata**: Metadata lists
- **Trakt**: Watch history and recommendations
- **Kodi Community**: Testing and feedback

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Report an issue](https://github.com/shiggsy365/AIOStreamsKODI/issues)

## Contribute

[<img src="https://www.thechaoticscot.com/wp-content/uploads/2020/04/kofi-banner.png">](https://ko-fi.com/shiggsy365)
