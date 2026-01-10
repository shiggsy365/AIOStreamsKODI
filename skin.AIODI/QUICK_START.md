# AIODI Skin Quick Start Guide

## Installation

### From Repository (Recommended)
1. Settings → Add-ons → Install from repository
2. AIOStreams Repository → Look and feel → Skins
3. AIODI - AIOStreams Integrated Skin → Install
4. Settings → Interface → Skin → Select AIODI

### From ZIP
1. Download: `skin.aiodi-1.0.0.zip`
2. Settings → Add-ons → Install from zip file
3. Select downloaded ZIP
4. Settings → Interface → Skin → Select AIODI

## First-Time Setup

1. **Install AIOStreams addon** (required)
   - Settings → Add-ons → Install from repository → AIOStreams Repository
   - Or manually install plugin.video.aiostreams

2. **Configure AIOStreams**
   - Open AIOStreams addon
   - Go to Settings → Accounts
   - Authorize Trakt (recommended for full widget functionality)

3. **Customize Widgets** (optional)
   - Settings → Widgets → Open Widget Configurator
   - Add/remove/reorder widgets for Home, Movies, and Shows pages

## Navigation

### Main Menu
- **Home** - Your personalized home with widgets
- **Movies** - Browse movies from AIOStreams
- **TV Shows** - Browse TV shows
- **Search** - Search for content
- **Settings** - Configure skin and AIOStreams

### Keyboard Shortcuts
- **Backspace** - Go back
- **Escape** - Close/Return to home
- **I** - Information dialog
- **C** - Context menu

## Widget Management

### Quick Access
Settings → Widgets → Open Widget Configurator

### Add Widget
1. Select page (Home/Movies/Shows)
2. Choose widget from Available list
3. Click "Add Widget"

### Remove Widget
1. Select widget in Active list
2. Click "Remove Widget"

### Reorder Widgets
1. Select widget in Active list
2. Use ↑↓ arrows to move

### Reset to Defaults
Settings → Widgets → Reset [Page] Widgets

## Available Widgets

### Trakt Integration
- Continue Watching
- Next Up
- Watchlist (Movies/Shows)
- Collection (Movies/Shows)

### Discovery
- Trending (Movies/Shows)
- Popular (Movies/Shows)
- Recommended (Movies/Shows)
- Anticipated (Movies/Shows)
- Most Watched (Movies/Shows)

## Customization

### Theme
Settings → General → Theme
- Default (Dodger Blue)
- Dark
- Light

### Visual Options
- Show fanart backgrounds
- Animate widgets
- Widget refresh interval

## Troubleshooting

### Widgets Not Showing
1. Verify AIOStreams is installed and working
2. Check Trakt authorization
3. Reset widgets: Settings → Widgets → Reset [Page] Widgets

### Content Not Playing
1. Check AIOStreams settings
2. Verify internet connection
3. Update AIOStreams to latest version

### Performance Issues
1. Reduce number of active widgets
2. Increase refresh interval
3. Disable widget animations

## Quick Tips

- **First Launch**: Widgets may take a moment to load content
- **Trakt Required**: Most widgets need Trakt authorization
- **Updates**: Skin updates automatically through repository
- **Context Menu**: Right-click on items for more options

## Getting Help

- GitHub: https://github.com/shiggsy365/AIOStreamsKODI/issues
- Check Kodi log: Settings → System → Logging
- Enable debug logging for detailed troubleshooting

## Version Updates

### For Developers
Use the automated update scripts:

**Windows:**
```powershell
.\Update-Skin-Version.ps1
```

**Linux/Mac:**
```bash
./update-skin-version.sh
```

See [SKIN_UPDATE_GUIDE.md](../SKIN_UPDATE_GUIDE.md) for details.

---

**Quick Reference Card**

| Action | Path |
|--------|------|
| Install Skin | Settings → Add-ons → Install from repository |
| Switch Skin | Settings → Interface → Skin → AIODI |
| Configure Widgets | Settings → Widgets → Open Widget Configurator |
| AIOStreams Settings | Settings → AIOStreams Integration |
| Reset Widgets | Settings → Widgets → Reset [Page] Widgets |

**Support**: AIOStreams addon required • Trakt recommended • Kodi 19+
