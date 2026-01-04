# AIOStreams Kodi Addon - Features Guide

## Table of Contents
1. [Dynamic Context Menus](#dynamic-context-menus)
2. [Stream Quality Filtering](#stream-quality-filtering)
3. [Stream Reliability Tracking](#stream-reliability-tracking)
4. [UI Enhancements](#ui-enhancements)
5. [Content Discovery](#content-discovery)
6. [Keyboard Shortcuts](#keyboard-shortcuts)
7. [Maintenance Tools](#maintenance-tools)
8. [Settings Reference](#settings-reference)

---

## Dynamic Context Menus

Right-click any movie or TV show to access dynamic context menus that change based on current state:

### Watchlist
- **Add to Watchlist** - Appears when item is NOT in watchlist
- **Remove from Watchlist** - Appears when item IS in watchlist

### Watch Status
- **Mark as Watched** - Appears for unwatched content
- **Mark as Unwatched** - Appears for watched content
- Works for: Movies, Shows, Seasons, Episodes

### Other Options
- **Play Trailer** - Watch YouTube trailer (if available)
- **Similar to this...** - Browse related/similar content
- **Quick Actions** - Fast access menu for common operations

---

## Stream Quality Filtering

### Automatic Quality Detection
Streams are analyzed for quality indicators:
- 4K / 2160p / UHD → 4K
- 1080p / FHD → Full HD
- 720p / HD → HD
- 480p → SD
- 360p, 240p → Low quality

### Quality Badges
Streams are displayed with color-coded quality indicators:
- `[COLOR magenta][4K][/COLOR]` - 4K content
- `[COLOR lime][1080p][/COLOR]` - Full HD
- `[COLOR cyan][720p][/COLOR]` - HD
- `[COLOR silver][SD][/COLOR]` - Standard definition

### Settings
**Settings → General → Quality Settings**
- **Preferred Quality**: Select your preferred quality (any, 4k, 1080p, 720p, 480p)
- **Minimum Quality**: Hide streams below this quality
- **Hide Low Quality Streams**: Enable to filter out low-quality streams

---

## Stream Reliability Tracking

### How It Works
The addon tracks which streams successfully play and which fail, building a reliability score over time.

### Reliability Icons
Streams are marked with star ratings:
- ★★★ - Excellent (90%+ success rate)
- ★★☆ - Good (70-89% success rate)
- ★☆☆ - Fair (50-69% success rate)
- ☆☆☆ - Poor (<50% success rate)

### Example Stream Display
```
★★★ [1080p] StreamProvider A - Fast Server
★★☆ [720p] StreamProvider B - Backup
★☆☆ [480p] StreamProvider C - Slow
```

### Preference Learning
Enable **Learn Stream Preferences** to have the addon remember which providers you prefer. Over time, your favorite providers will appear first in the list.

### Data Storage
- Statistics stored in: `addon_data/plugin.video.aiostreams/stream_stats.json`
- Preferences stored in: `addon_data/plugin.video.aiostreams/stream_prefs.json`
- Clear via: **Settings → Advanced → Maintenance**

---

## UI Enhancements

### Color-Coded Items
Items are color-coded based on watch status (if enabled):
- **Blue** - Watched content
- **Gold** - In-progress content (partially watched)
- **White** - Unwatched content

### Progress Bars
Visual progress indicators show how much you've watched:
```
Season 1 (10 episodes) [████████░░] 85% (8/10)
5. Episode Title [████████░░] 85%
```

### Season Display
```
[COLOR blue]Season 1 (10 episodes)[/COLOR] ✓
[COLOR gold]Season 2 (10 episodes)[/COLOR] [████░░░░░░] 4/10
[COLOR white]Season 3 (10 episodes)[/COLOR]
```

### Episode Display
```
[COLOR blue]1. Pilot[/COLOR]
[COLOR blue]2. Second Episode[/COLOR]
[COLOR gold]3. Third Episode[/COLOR] [████████░░] 85%
[COLOR white]4. Fourth Episode[/COLOR]
```

### Settings
**Settings → User Interface**
- **Show Progress Bars**: Enable/disable progress indicators
- **Color Code by Watch Status**: Enable/disable color coding
- **Show Quality Badges**: Show/hide quality labels
- **Show Reliability Icons**: Show/hide star ratings

---

## Content Discovery

### Similar Content
Find movies and TV shows similar to what you're watching.

**How to Use:**
1. Right-click any movie or TV show
2. Select **"Similar to this..."**
3. Browse related content curated by Trakt

**Powered by:** Trakt's recommendation algorithm

### Quick Access
- Available in context menu for all content
- Uses Trakt's `/related` endpoint
- Shows up to 20 related items

---

## Keyboard Shortcuts

### Quick Actions Menu
Press **A** while browsing to open the Quick Actions menu:
- Add to Watchlist (Q)
- Mark as Watched (W)
- Show Info (I)
- Similar Content (S)
- Play (Enter)

### Individual Shortcuts
- **Q** - Toggle Watchlist
- **W** - Mark as Watched
- **I** - Show Info
- **S** - Similar Content

### Setup Instructions
1. Copy `keymap.xml.template` to `userdata/keymaps/aiostreams.xml`
2. Restart Kodi
3. Shortcuts are now active while browsing AIOStreams

### Custom Keymaps
Edit `userdata/keymaps/aiostreams.xml` to customize shortcuts to your preference.

---

## Maintenance Tools

**Settings → Advanced → Maintenance**

### Clear Cache
Removes all cached metadata. Use if:
- Metadata seems outdated
- Images not loading correctly
- Want to free up disk space

### Clear Stream Statistics
Resets all stream reliability data. Use if:
- Want to start fresh with stream tracking
- Reliability scores seem incorrect
- Changed stream providers

### Clear Learned Preferences
Resets provider preference learning. Use if:
- Want the addon to "forget" your preferences
- Trying different providers
- Preference sorting seems off

### Test AIOStreams Connection
Diagnostic tool that shows:
- Connection status (success/failure)
- Server response time
- Number of available catalogs

Example output:
```
✓ Connection successful!

Server: https://your-server.com
Response time: 0.23s
Catalogs available: 15
```

---

## Settings Reference

### General Settings

**Playback Settings**
- `default_behavior`: Play First Stream | Show Streams (default)
- `fallback_behavior`: Play Next | Show Streams (when first stream fails)

**Quality Settings**
- `preferred_quality`: any | 4k | 1080p | 720p | 480p
- `min_quality`: 240p | 360p | 480p | 720p | 1080p
- `filter_low_quality`: Hide streams below minimum quality

**Resume & Progress**
- `auto_resume`: Resume playback from last position
- `auto_mark_watched_percent`: Mark as watched at X% (default: 90%)

### User Interface

**Display Options**
- `show_progress_bars`: Show visual progress indicators
- `color_code_items`: Color code by watch status
- `show_quality_badges`: Show quality labels on streams
- `show_reliability_icons`: Show star ratings on streams
- `learn_preferences`: Learn and prioritize preferred providers

### Advanced Settings

**Performance**
- `cache_expiry_hours`: How long to cache metadata (default: 24)
- `max_streams_to_show`: Maximum streams in selection dialog (default: 20)
- `stream_test_timeout`: Timeout for stream testing in seconds (default: 5)

**Debug**
- `debug_logging`: Enable detailed logging for troubleshooting

---

## Tips & Tricks

### Best Stream Quality
1. Set **Preferred Quality** to your connection capability
2. Enable **Hide Low Quality Streams**
3. Let reliability tracking run for a few days
4. Best streams will automatically appear first

### Faster Browsing
1. Disable **Color Code Items** if Trakt is slow
2. Increase **Cache Expiry Hours** to reduce API calls
3. Reduce **Max Streams to Show** for faster stream selection

### Accurate Watch History
1. Enable **Auto Resume Playback**
2. Set **Mark Watched at %** to 85-90%
3. Enable **Trakt Scrobbling** for automatic tracking

### Content Discovery
1. Use **Similar to this...** to find related content
2. Check **Trakt Recommended** for personalized suggestions
3. Browse **Trending** for what's popular

---

## Support

For issues, feature requests, or questions:
- GitHub: [Report Issue](https://github.com/your-repo/issues)
- Kodi Forum: [AIOStreams Thread](https://forum.kodi.tv/)

---

**Version:** 1.0.0
**Last Updated:** 2026-01-04
