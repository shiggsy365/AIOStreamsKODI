# AIOStreams Kodi Plugin Documentation

## Overview

**AIOStreams** is a powerful Kodi video plugin that connects to your self-hosted AIOStreams backend, providing seamless access to streaming content with advanced features like Trakt synchronization, intelligent stream selection, and comprehensive metadata integration.

### What Does AIOStreams Do?

AIOStreams acts as a frontend client for your [AIOStreams backend](https://github.com/Viren070/aiostreams), bringing powerful streaming aggregation directly into your Kodi media center:

- **🎬 Content Discovery**: Browse catalogs, search movies/TV shows, and discover trending content
- **📺 Trakt Integration**: Full sync with watchlist, collections, watch history, and Next Up
- **🎯 Smart Stream Selection**: Automatic quality filtering, reliability tracking, and preference learning
- **⏭️ Autoplay Next Episode**: Configurable auto-play with background stream pre-loading
- **🎨 Rich Metadata**: TMDb/TVDb integration with posters, fanart, cast information, and ratings
- **🌐 Subtitle Support**: Automatic subtitle scraping via AIOStreams backend
- **🎥 Trailer Playback**: YouTube trailer integration for content preview

---

## Required Configuration

### 1. AIOStreams Backend

You **must** have a running AIOStreams instance configured with:

#### Required Components:
- **Metadata Provider**: Must use a provider that serves **IMDB tags**
  - **Recommended**: [AIOMetadata](https://github.com/cedya77/aiometadata) for stability and reliability
  - AIOMetadata provides rich metadata, catalog support, and IMDB ID integration
  
- **Search Provider**: Configure at least one search provider
  - AIOMetadata (recommended) provides unified search across content types
  
- **Scraper**: At least one torrent indexer or debrid service configured

#### Backend Setup:
1. Deploy AIOStreams (self-hosted or via ElfHosted)
2. Configure AIOMetadata as your metadata provider
3. Set up scrapers (torrent indexers, debrid services)
4. Ensure IMDB tags are enabled in metadata responses

### 2. Plugin Settings

Access settings via: **Add-ons → Video add-ons → AIOStreams → Right-click → Settings**

#### Essential Settings:

**General**
- **AIOStreams Host URL**: Your backend URL (e.g., `https://aiostreams.elfhosted.com`)
- **API Timeout**: Request timeout in seconds (default: 30)

**Playback**
- **Preferred Quality**: Set your preferred stream quality (4K, 1080p, 720p, etc.)
- **Minimum Quality**: Lowest acceptable quality (filters out lower quality streams)
- **Auto-play**: Enable automatic stream selection based on preferences

**Trakt Integration** (Optional)
- **Enable Trakt**: Authorize your Trakt account for sync features
- **Auto-Sync**: Automatic synchronization of watch history and progress
- **Sync Interval**: How often to sync with Trakt (default: 5 minutes)

---

## Custom Formatter Option

AIOStreams supports **custom stream title formatting** to display stream information exactly how you want it.

### Enabling Custom Formatting

1. Go to: **Settings → Playback → Stream Display**
2. Enable **"Use Custom Formatter"**
3. Enter your custom format string

### Format Specification

Use the following placeholders in your format string:

#### Available Placeholders:

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{quality}` | Stream quality | `1080p`, `720p`, `4K` |
| `{source}` | Source/provider name | `Torrentio`, `RealDebrid` |
| `{size}` | File size | `2.5 GB`, `850 MB` |
| `{codec}` | Video codec | `H.264`, `H.265`, `AV1` |
| `{audio}` | Audio codec | `AAC`, `DTS`, `Dolby Atmos` |
| `{language}` | Audio language | `English`, `Multi` |
| `{seeders}` | Number of seeders (torrents) | `45`, `120` |
| `{reliability}` | Provider reliability rating | `★★★★☆` |

#### Example Format Strings:

**Default Format:**
```
[{quality}] {source} - {size}
```
Output: `[1080p] Torrentio - 2.5 GB`

**Detailed Format:**
```
{quality} | {codec} {audio} | {source} ({reliability}) | {size}
```
Output: `1080p | H.265 AAC | Torrentio (★★★★☆) | 2.5 GB`

**Compact Format:**
```
{quality} {source} {size}
```
Output: `1080p Torrentio 2.5GB`

### Tips for Custom Formatting:

- Use `|` or `-` as separators for readability
- Include `{reliability}` to see provider success rates
- Add `{seeders}` for torrent streams to gauge availability
- Keep formats concise for better display on smaller screens

---

## Optional Skin

While AIOStreams works with any Kodi skin, we offer **AIODI** - a custom skin designed specifically for AIOStreams integration.

### Why Use AIODI Skin?

- **Seamless Integration**: Built-in widget support for AIOStreams catalogs
- **Widget Manager**: Easy-to-use interface for customizing your home screen
- **Trakt Widgets**: Dedicated Next Up and Watchlist widgets
- **YouTube Trailers**: Integrated trailer playback from home screen
- **IMVDb Support**: MTV-style music video browsing
- **Modern Design**: Clean, responsive interface optimized for streaming

**Learn more**: See [AIODI Skin Documentation](SKIN_DOCUMENTATION.md)

---

## Installation

### From Repository (Recommended)

1. Add repository to Kodi: `https://shiggsy365.github.io/AIOStreamsKODI/`
2. Go to: **Settings → Add-ons → Install from repository**
3. Select **AIOStreams Repository → Video add-ons → AIOStreams**
4. Click **Install**

### From Zip File

1. Download latest release from [GitHub Releases](https://github.com/shiggsy365/AIOStreamsKODI/releases)
2. Go to: **Settings → Add-ons → Install from zip file**
3. Select the downloaded `.zip` file

---

## Quick Start Guide

1. **Install the plugin** (see Installation above)
2. **Configure AIOStreams backend** with AIOMetadata
3. **Open plugin settings** and enter your backend URL
4. **(Optional) Authorize Trakt** for sync features
5. **Browse catalogs** or search for content
6. **Select a stream** and enjoy!

---

## Troubleshooting

### No Streams Found
- Verify your AIOStreams backend is running and accessible
- Check that scrapers are configured in your backend
- Ensure metadata provider (AIOMetadata) is properly configured

### IMDB ID Errors
- Confirm your metadata provider serves IMDB tags
- AIOMetadata is recommended for reliable IMDB ID support
- Check backend logs for metadata provider errors

### Trakt Sync Issues
- Re-authorize Trakt in plugin settings
- Check Trakt API status at [trakt.tv/status](https://trakt.tv/status)
- Verify auto-sync interval isn't too aggressive (minimum 5 minutes)

---

## Support the Project

If you find AIOStreams useful, consider supporting development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/shiggsy365)

---

**Version**: 1.1.210  
**Last Updated**: 2026-01-19  
**License**: MIT

**Powered by**:
- [AIOStreams](https://github.com/Viren070/aiostreams) by Viren070
- [AIOMetadata](https://github.com/cedya77/aiometadata) by Cedya77
