# AIODI Skin Testing Instructions

The AIODI skin has been successfully added to your AIOStreams Kodi repository and is ready for testing!

## Repository Location

The skin is now available in your Kodi repository at:
- **Repository**: docs/repository.aiostreams/zips/
- **Skin Package**: skin.aiodi-1.0.0.zip (22KB)
- **Branch**: claude/implement-custom-skin-PlwEs

## Files Added to Repository

```
docs/repository.aiostreams/zips/
├── addons.xml (updated with skin.aiodi entry)
├── addons.xml.md5 (updated checksum)
└── skin.aiodi/
    ├── skin.aiodi-1.0.0.zip
    ├── skin.aiodi-1.0.0.zip.md5
    └── README.md
```

## How to Test in Kodi

### Method 1: Install from Repository (After Merging to Main)

Once you merge this branch to main, the skin will be available through your AIOStreams repository:

1. **Open Kodi**
2. Go to **Settings** (gear icon)
3. Select **Interface**
4. Click **Skin**
5. Click **Get more...**
6. Look for **AIODI - AIOStreams Integrated Skin**
7. Click to install
8. When prompted, select **Yes** to switch to the new skin

### Method 2: Manual Installation (For Testing Now)

To test the skin immediately without waiting for the merge:

1. **Download the ZIP file** from the branch:
   ```
   https://github.com/shiggsy365/AIOStreamsKODI/raw/claude/implement-custom-skin-PlwEs/docs/repository.aiostreams/zips/skin.aiodi/skin.aiodi-1.0.0.zip
   ```

2. **Install in Kodi**:
   - Go to Settings → Add-ons
   - Click "Install from zip file"
   - Navigate to the downloaded ZIP
   - Select skin.aiodi-1.0.0.zip
   - Wait for "Add-on installed" notification

3. **Switch to the Skin**:
   - Go to Settings → Interface → Skin
   - Select "AIODI - AIOStreams Integrated Skin"
   - Click "Yes" to confirm the switch

### Method 3: Direct File Copy (For Development)

For quick testing during development:

1. **Copy the skin directory**:
   ```bash
   cp -r skin.AIODI ~/.kodi/addons/skin.aiodi
   ```

   Or on Windows:
   ```
   xcopy skin.AIODI %APPDATA%\Kodi\addons\skin.aiodi /E /I
   ```

2. **Restart Kodi**

3. **Switch to the skin** from Settings → Interface → Skin

## Prerequisites

Before testing, ensure you have:

1. ✅ **Kodi 19 (Matrix) or higher** installed
2. ✅ **AIOStreams addon (v1.5.0+)** installed and configured
3. ✅ **Trakt account** authorized in AIOStreams (recommended)
4. ✅ **Script.module.requests** addon installed

## What to Test

### Basic Functionality
- [ ] Skin loads without errors
- [ ] Home screen displays correctly
- [ ] Navigation bar works (Home, Movies, Shows, Search, Settings)
- [ ] Widgets appear on home screen

### Widget System
- [ ] Default widgets load (Continue Watching, Trending Movies, etc.)
- [ ] Widget content displays from AIOStreams
- [ ] Horizontal scrolling works in widgets
- [ ] Widget items are clickable and play content

### Widget Configurator
- [ ] Open configurator from Settings → Widgets → Open Widget Configurator
- [ ] Page selector works (Home, Movies, Shows)
- [ ] Available widgets list displays all 15+ widget types
- [ ] Add Widget button adds widgets to active list
- [ ] Remove Widget button removes widgets
- [ ] Up/Down arrows reorder widgets
- [ ] Save button persists changes
- [ ] Reset button restores defaults

### AIOStreams Integration
- [ ] Content plays correctly from widgets
- [ ] Context menus work (Add to Watchlist, etc.)
- [ ] Trakt progress syncs correctly
- [ ] Search functionality works
- [ ] Movie/TV show navigation works

### Visual Elements
- [ ] Colors and fonts display correctly
- [ ] Focused items highlight properly
- [ ] Dialog boxes (OK, Yes/No, Busy) display correctly
- [ ] Backgrounds and overlays render properly

### Performance
- [ ] Skin loads quickly
- [ ] No lag when navigating widgets
- [ ] Background service runs without issues
- [ ] Widget updates occur properly

## Known Limitations

1. **Media Assets**: The skin currently uses placeholder asset paths. If you see broken images:
   - Icon and fanart images need to be created
   - Common assets (white.png, border.png) need to be added to media/common/
   - This is cosmetic and doesn't affect functionality

2. **Font Files**: The skin references Roboto fonts which should be available in Kodi by default. If fonts don't display correctly, the font file paths may need adjustment.

3. **Incomplete Windows**: Some standard Kodi windows (like detailed movie info) may fall back to default views. Additional XML files can be added for complete coverage.

## Troubleshooting

### Skin Won't Load
- Check Kodi version (must be 19+)
- Verify AIOStreams addon is installed
- Check Kodi log for errors: Settings → System → Logging

### Widgets Don't Show Content
- Verify AIOStreams addon is working
- Check Trakt authorization in AIOStreams settings
- Verify internet connection
- Try resetting widgets: Settings → Widgets → Reset [Page] Widgets

### Background Service Not Running
- Check service.py for syntax errors
- Verify Python version compatibility (Python 3)
- Check Kodi logs for service errors

### Widget Configurator Won't Open
- Verify widget_manager.py exists in scripts/
- Check for Python syntax errors
- Try restarting Kodi

## Reporting Issues

When reporting issues, please include:
1. Kodi version and platform (Windows/Linux/Android/etc.)
2. AIOStreams addon version
3. Steps to reproduce the issue
4. Kodi log file (kodi.log) with debug logging enabled
5. Screenshots if visual issues

## Next Steps After Testing

1. **Gather Feedback**: Document what works and what needs improvement
2. **Add Media Assets**: Create icon, fanart, and UI element images
3. **Complete Additional Windows**: Add movie/TV info dialogs, settings windows
4. **Performance Tuning**: Optimize widget loading and caching
5. **Polish**: Add animations, transitions, and visual enhancements
6. **Documentation**: Create video tutorials and user guides

## Support

For questions or issues:
- GitHub Issues: https://github.com/shiggsy365/AIOStreamsKODI/issues
- Branch: claude/implement-custom-skin-PlwEs

---

**Happy Testing! 🎬**
