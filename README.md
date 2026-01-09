# AIOStreams Kodi Addon

A powerful Kodi addon for streaming content from AIOStreams with comprehensive Trakt integration, intelligent stream selection, and advanced playback features.

---

## Overview

AIOStreams Kodi Addon is a feature-rich video plugin that integrates the [AIOStreams](https://github.com/Viren070/aiostreams) backend with Kodi's media center interface. It provides seamless access to streaming content with advanced features like Trakt synchronization, stream quality filtering, reliability tracking, and TMDBHelper integration for enhanced content discovery.

### What is AIOStreams?

[AIOStreams](https://github.com/Viren070/aiostreams) is a self-hosted streaming aggregator that:
- Scrapes content from multiple sources (torrent indexers, debrid services, etc.)
- Provides unified search across streaming providers
- Offers metadata integration via TMDb/TVDb
- Supports subtitle scraping
- Can be hosted locally or via services like ElfHosted

This Kodi addon acts as a frontend client to your AIOStreams backend, bringing all that functionality into your Kodi media center.

---

## Key Features

### 🎬 Content Access
- **Browse Catalogs**: Access all AIOStreams catalogs (Movies, TV Shows, Popular, Trending, etc.)
- **Advanced Search**: Tabbed search interface with separate Movies/TV Shows/All Results views
- **Rich Metadata**: TMDb/TVDb integration including posters, fanart, cast, ratings
- **Subtitle Support**: Automatic subtitle scraping via AIOStreams backend
- **Trailer Playback**: YouTube trailer integration for content preview

### 📺 Trakt Integration
- **Full Sync**: Watchlist, collections, watch history, and progress tracking
- **Next Up**: Smart list showing next unwatched episodes from your watched shows
- **Continue Watching**: Resume partially watched content with progress indicators
- **Dynamic Context Menus**: Right-click actions that adapt based on watch status
- **Auto-Scrobbling**: Automatic playback tracking to Trakt
- **Delta Sync**: Intelligent sync only downloads changed data (90%+ API reduction)

### 🎯 Stream Management
- **Quality Filtering**: Set preferred and minimum quality levels (4K, 1080p, 720p, etc.)
- **Reliability Tracking**: Star ratings show success rates for each provider
- **Preference Learning**: Addon learns which providers you prefer and sorts accordingly
- **Smart Sorting**: Streams sorted by quality → reliability → learned preferences
- **Quality Badges**: Color-coded quality indicators ([4K], [1080p], [720p])
- **Fallback Options**: Automatic retry with next stream on playback failure

### ⏭️ Autoplay Next Episode
- **Configurable Timing**: Set when autoplay dialog appears based on episode length:
  - Shows under 15 minutes (default: 20s before end)
  - Shows under 30 minutes (default: 30s before end)
  - Shows under 45 minutes (default: 45s before end)
  - Shows over 45 minutes (default: 60s before end)
- **Background Scraping**: Streams pre-loaded 10 seconds before dialog appears
- **User Control**: Interactive dialog with "Play Now" or "Stop Watching" buttons
- **Countdown Timer**: 10-second countdown before auto-playing next episode
- **Smart Detection**: Only activates for TV shows (not movies)

### 🎨 UI Enhancements
- **Progress Bars**: Visual indicators showing watch progress for episodes/seasons
- **Color Coding**: Blue (watched), Gold (in-progress), White (unwatched)
- **Loading Screens**: Progress dialogs during stream scraping
- **Episode Thumbnails**: Show-specific thumbnails for continue watching
- **Keyboard Shortcuts**: Optional keymaps for quick actions (Q, W, I, S, A)

### ⚡ Performance
- **SQLite Database**: Local caching reduces API calls by 95%+
- **Stream Pre-loading**: Caches first 3 Next Up items with 15-minute TTL
- **Metadata Caching**: Configurable cache expiry (default 24 hours)
- **Throttled Sync**: 5-minute throttle prevents excessive Trakt API calls
- **Widget Support**: Optimized for use as Kodi home screen widgets

---

## Quick Start

### 1. Prerequisites
You need a running **AIOStreams instance** configured with:
- At least one scraper (torrent indexer or debrid service)
- Search provider (recommend [AIOMetadata](https://github.com/cedya77/aiometadata))
- Metadata source (recommend AIOMetadata)

### 2. Install Addon

**From Repository** (Recommended):
1. Add repository to Kodi: `https://shiggsy365.github.io/AIOStreamsKODI/`
2. Install from: Settings → Add-ons → Install from repository → AIOStreams Repository

**From Zip** (Manual):
1. Download latest release from [Releases](https://github.com/shiggsy365/AIOStreamsKODI/releases)
2. Install via: Settings → Add-ons → Install from zip file

### 3. Configure
1. Open addon settings: Add-ons → Video add-ons → AIOStreams → Right-click → Settings
2. Set **AIOStreams Host URL** (e.g., `https://aiostreams.elfhosted.com`)
3. (Optional) Configure Trakt integration for sync features

**For detailed installation and configuration**, see [INSTALLATION.md](INSTALLATION.md)

---

## Documentation

- **[INSTALLATION.md](INSTALLATION.md)** - Complete installation guide and settings reference
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture, AIOStreams/AIOMetadata details, custom templates
- **[FEATURES.md](plugin.video.aiostreams/FEATURES.md)** - Detailed feature documentation

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
Right-click any movie/show for quick access to:
- Play / Show Streams
- Add/Remove from Watchlist
- Mark as Watched/Unwatched
- Play Trailer
- Similar Content
- Quick Actions Menu

---

## Requirements

### Backend
- **AIOStreams** instance (self-hosted or ElfHosted)
- **AIOMetadata** (recommended) for search and metadata

### Kodi
- **Kodi 19+** (Matrix/Nexus/Omega) - Python 3 support required
- **script.module.requests** (auto-installed)

### Optional
- **Trakt Account** for sync features
- **TMDBHelper** for enhanced content discovery
- **resource.fonts.noto-emoji** for enhanced emoji rendering

---

## Support

**Issue Reporting:**
- GitHub Issues: [Report an issue](https://github.com/shiggsy365/AIOStreamsKODI/issues)

**Contribution:**

[<img src="https://github.com/shiggsy365/AIOStreamsKODI/blob/main/.github/support_me_on_kofi_red.png?raw=true">](https://ko-fi.com/shiggsy365)

---

## License

MIT License - See [LICENSE](LICENSE) for details

---

**Version**: 3.5.5
**Last Updated**: 2026-01-09

---

### Acknowledgments

This addon is powered by the incredible work of:

- **[AIOStreams](https://github.com/Viren070/aiostreams)** by [Viren070](https://github.com/Viren070) - The streaming aggregation backend that makes this all possible
- **[AIOMetadata](https://github.com/cedya77/aiometadata)** by [Cedya77](https://github.com/cedya77) - Metadata and catalog provider for rich content information

Special thanks to the Kodi community for testing and feedback!

**Support the ecosystem:**

[<img src="https://github.com/shiggsy365/AIOStreamsKODI/blob/main/.github/support_me_on_kofi_red.png?raw=true">](https://ko-fi.com/shiggsy365)
