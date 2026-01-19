# AIODI Skin Documentation

## Overview

**AIODI** (AIOStreams Optimized Display Interface) is a modern, feature-rich Kodi skin designed specifically for seamless integration with the AIOStreams plugin. Built from the ground up for streaming enthusiasts, AIODI combines elegant design with powerful functionality.

---

## Key Features

### 🎬 AIOStreams Plugin Integration

AIODI is purpose-built for AIOStreams, providing:

- **Native Widget Support**: Display AIOStreams catalogs directly on your home screen
- **Dynamic Content Loading**: Widgets automatically update with fresh content
- **Smart Caching**: Efficient content loading with minimal API calls
- **Seamless Navigation**: Optimized navigation flow for browsing and playback
- **Info Panel Integration**: Rich metadata display with cast, trailers, and related content
- **Context Menus**: Quick actions for watchlist, watched status, and playback

#### Widget Features:
- **Catalog Widgets**: Display any AIOStreams catalog (Trending, Popular, Genre-specific)
- **More Results Button**: Pagination support - click to load next 20 items
- **Custom Artwork**: Poster and landscape layouts with clearlogo support
- **Progress Indicators**: Visual progress bars for partially watched content
- **Watched Overlays**: Green checkmarks for completed content

---

### 📋 Simple Widget Manager

Customize your home screen with an intuitive widget management system:

#### Features:
- **Drag-and-Drop Interface**: Reorder widgets with simple up/down controls
- **Multi-Page Support**: Organize widgets across Home, Movies, and TV Shows pages
- **Live Preview**: See widget labels and content types before adding
- **Duplicate Prevention**: Automatic detection prevents adding the same widget twice
- **Persistent Configuration**: Widget layout saved and restored across sessions

#### How to Use:
1. Open **Widget Manager** from the side menu
2. Select a page (Home, Movies, or TV Shows)
3. Choose **Add Widget** to browse available catalogs
4. Select a catalog to add it to the current page
5. Use **Move Up/Down** to reorder widgets
6. Click **Save** to apply changes

#### Available Widget Types:
- **AIOStreams Catalogs**: Trending, Popular, Genre-based, Network-specific
- **Trakt Widgets**: Next Up, Watchlist, Collection
- **Custom Widgets**: Configure your own catalog combinations

---

### 🎥 YouTube Integration for Trailers

Watch trailers without leaving your home screen:

#### Features:
- **One-Click Playback**: Click the trailer button to instantly play
- **YouTube Plugin Integration**: Seamless integration with YouTube addon
- **Automatic Trailer Discovery**: Fetches official trailers from YouTube
- **Fallback Support**: Displays "No Trailer Available" when none found
- **Info Panel Trailers**: Watch trailers from the detailed info screen

#### Requirements:
- **YouTube Kodi Plugin** must be installed
- Internet connection for YouTube access

---

### 📺 Trakt Integration

Full Trakt synchronization with dedicated widgets and features:

#### Next Up Widget
- **Smart Episode Detection**: Shows next unwatched episode from your watched shows
- **Progress Tracking**: Visual indicators show watch progress
- **Zero API Calls**: Pure SQL-based, instant loading
- **Auto-Refresh**: Updates when you mark episodes as watched

#### Watchlist Widgets
- **Separate Movie/TV Widgets**: Dedicated widgets for movies and series
- **Real-Time Sync**: Automatically syncs with Trakt every 5 minutes
- **Add/Remove Actions**: Quick context menu actions to manage watchlist
- **Database-First**: Instant loading from local cache

#### Watched Status Integration
- **Info Panel Buttons**: Toggle watched/watchlist status from info screen
- **Visual Indicators**: Green checkmarks for watched content
- **Automatic Refresh**: Widgets update immediately after status changes
- **Sync Across Devices**: Changes sync to Trakt and all connected devices

#### Features:
- **Automatic Scrobbling**: Playback automatically tracked to Trakt
- **Collection Support**: View and manage your Trakt collection
- **Hidden Items**: Hide shows from progress tracking
- **Delta Sync**: Only downloads changed data (90%+ API reduction)

---

### 🎵 IMVDb Integration

Experience music videos MTV-style with IMVDb plugin integration:

#### Features:
- **Dedicated Music Page**: Full page for music video browsing
- **IMVDb Widget**: Display music videos on your home screen
- **Direct Playback**: Click to play music videos instantly
- **Artist/Song Search**: Search for specific music videos
- **Curated Collections**: Browse by genre, year, or popularity

#### Requirements:
- **IMVDb Kodi Plugin** must be installed
- IMVDb API key (free registration)

#### How to Use:
1. Navigate to **Music** page from side menu
2. Browse IMVDb widget for featured music videos
3. Click any video to play instantly
4. Use search to find specific artists or songs

---

## User Interface

### Side Menu Navigation

The left-side menu provides quick access to all features:

- **Logo Button**: User profile/logout
- **Search**: Global search across all content
- **Home**: Main landing page with featured widgets
- **TV Shows**: TV series catalogs and widgets
- **Movies**: Movie catalogs and widgets
- **Music**: IMVDb music video browser
- **Settings**: Skin and plugin configuration

### Home Screen Layout

- **Top Section**: Featured content with clearlogo and metadata
- **Widget Rows**: Scrollable horizontal rows of content
- **Background**: Solid black for optimal contrast (no distracting fanart)
- **Navigation**: Up/down to switch widgets, left/right to browse items

### Info Panel

Detailed information screen with:
- **Metadata**: Title, plot, year, rating, runtime, genres
- **Cast**: Top 5 cast members with photos
- **Buttons**: Play, Trailer, Watchlist, Watched
- **Related Content**: Similar movies/shows
- **Dynamic Icons**: Buttons show current status (tick = in watchlist/watched)

---

## Visual Design

### Modern Aesthetics
- **Clean Layout**: Minimalist design focuses on content
- **Smooth Animations**: Polished transitions and hover effects
- **Color Coding**: Blue (watched), Gold (in-progress), White (unwatched)
- **High Contrast**: Black background with vibrant content posters
- **Responsive**: Optimized for 1080p and 4K displays

### Custom Graphics
- **New Logo**: Custom AIODI branding with lightning bolt
- **More Results Icon**: Custom pagination button
- **Button Icons**: Consistent iconography across all actions
- **Progress Bars**: Visual indicators for watch progress

---

## Configuration

### Widget Manager Settings

Access via: **Side Menu → Widget Manager**

- **Add Widgets**: Browse and add AIOStreams catalogs
- **Reorder**: Move widgets up/down within a page
- **Remove**: Delete unwanted widgets
- **Reset**: Clear all widgets and start fresh

### Skin Settings

Access via: **Settings → Skin Settings**

- **Home Screen**: Configure default focus and behavior
- **Widget Display**: Adjust item counts and layouts
- **Navigation**: Customize menu behavior
- **Appearance**: Color schemes and visual options

---

## Tips & Tricks

### Optimizing Performance
- **Limit Widgets**: Keep 5-8 widgets per page for best performance
- **Use Trakt Widgets**: Database-first widgets load instantly
- **Clear Cache**: Periodically clear plugin cache for fresh content

### Customization Ideas
- **Genre Pages**: Create genre-specific widget pages (Action, Comedy, etc.)
- **Network Pages**: Organize by streaming service (Netflix, HBO, etc.)
- **Mood Boards**: Curate widgets by mood (Feel-Good, Thriller, etc.)

### Keyboard Shortcuts
- **Arrow Keys**: Navigate menus and widgets
- **Enter**: Select/Play content
- **Backspace**: Go back
- **C**: Open context menu
- **I**: Open info panel

---

## Requirements

### Kodi Version
- **Kodi 19+** (Matrix, Nexus, or Omega)
- Python 3 support required

### Required Plugins
- **AIOStreams Plugin**: Core functionality
- **YouTube Plugin**: For trailer playback

### Optional Plugins
- **IMVDb Plugin**: Music video integration
- **TMDBHelper**: Enhanced content discovery

---

## Installation

### From Repository (Recommended)

1. Add repository: `https://shiggsy365.github.io/AIOStreamsKODI/`
2. Go to: **Settings → Add-ons → Install from repository**
3. Select **AIOStreams Repository → Look and Feel → Skin → AIODI**
4. Click **Install**
5. When prompted, click **Yes** to switch to AIODI skin

### From Zip File

1. Download latest release from [GitHub Releases](https://github.com/shiggsy365/AIOStreamsKODI/releases)
2. Go to: **Settings → Add-ons → Install from zip file**
3. Select `skin.AIODI-X.X.X.zip`
4. Switch to AIODI skin when prompted

---

## Troubleshooting

### Widgets Not Loading
- Verify AIOStreams plugin is installed and configured
- Check that widget_config.json exists in addon_data
- Try removing and re-adding the widget

### YouTube Trailers Not Playing
- Install YouTube plugin from Kodi repository
- Verify YouTube plugin is enabled
- Check internet connection

### IMVDb Not Showing
- Install IMVDb plugin
- Configure IMVDb API key in plugin settings
- Restart Kodi after installation

### Black Screen on Home
- Check that at least one widget is configured
- Verify AIOStreams backend is accessible
- Clear Kodi cache and restart

---

## Support the Project

If you enjoy AIODI skin, please consider supporting development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/shiggsy365)

---

**Version**: 6.0.474  
**Last Updated**: 2026-01-19  
**License**: MIT

**Built for**: AIOStreams Plugin  
**Optimized for**: 1080p and 4K displays
