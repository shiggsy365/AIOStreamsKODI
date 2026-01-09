# AIODI - AIOStreams Integrated Dynamic Interface

A custom Kodi skin designed specifically for deep AIOStreams integration with dynamic widget management and a clean, Netflix-style interface.

## Features

### 🎯 Deep AIOStreams Integration
- Native content browsing without navigating through addon menus
- Direct access to all AIOStreams features from the home screen
- Seamless Trakt integration for watchlists, collections, and progress tracking

### 🎨 Dynamic Widget System
- Customizable home screen widgets
- Drag-and-drop widget configuration
- Support for multiple widget types:
  - Continue Watching
  - Trending Movies & TV Shows
  - Popular content
  - Watchlists
  - Collections
  - Recommendations
  - And more...

### ⚙️ Easy Configuration
- Visual widget configurator (Settings → Widgets → Open Widget Configurator)
- Per-page widget customization (Home, Movies, Shows)
- Quick reset to defaults
- Background service for automatic updates

### 🎬 Netflix-Style Interface
- Clean, modern design
- Focus on content discovery
- Horizontal scrolling widgets
- Large poster artwork
- Smooth animations

## Requirements

- Kodi 19 (Matrix) or higher
- **AIOStreams addon** (version 1.5.0 or higher) - **REQUIRED**
- Trakt account (recommended for full functionality)

## Installation

### Method 1: From Repository (Recommended)
1. Install the AIOStreams addon first if you haven't already
2. Download the AIODI skin from the repository
3. Go to Settings → Interface → Skin
4. Select AIODI from the list
5. Click "Yes" to switch to the skin

### Method 2: Manual Installation
1. Download the skin.aiodi folder
2. Copy it to your Kodi addons directory:
   - Windows: `%APPDATA%\Kodi\addons\`
   - Linux: `~/.kodi/addons/`
   - macOS: `~/Library/Application Support/Kodi/addons/`
3. Restart Kodi
4. Go to Settings → Interface → Skin
5. Select AIODI

## First-Time Setup

After installing the skin:

1. **Install AIOStreams** if not already installed
2. **Configure AIOStreams** (Settings → AIOStreams Integration → Open AIOStreams Settings)
3. **Authorize Trakt** in AIOStreams settings for full widget functionality
4. **Customize Widgets** (Settings → Widgets → Open Widget Configurator)

## Widget Configuration

### Opening the Widget Configurator
- Go to Settings → Widgets → Open Widget Configurator
- Or press the Settings button from the home screen

### Adding Widgets
1. Select the page you want to configure (Home, Movies, or Shows)
2. Browse the "Available Widgets" list
3. Select a widget and click "Add Widget"
4. The widget will appear in the "Active Widgets" list

### Removing Widgets
1. Go to the "Active Widgets" list
2. Select the widget you want to remove
3. Click "Remove Widget"

### Reordering Widgets
1. Select a widget in the "Active Widgets" list
2. Use the up/down arrows to change its position
3. Widgets appear on screen in the order shown in the list

### Resetting to Defaults
- Settings → Widgets → Reset [Page] Widgets
- This will restore the default widget configuration for that page

## Available Widgets

### Trakt Widgets
- **Continue Watching** - Resume your in-progress shows and movies
- **Next Up** - Next episodes in your watched series
- **Watchlist** - Your Trakt watchlist items
- **Collection** - Items in your Trakt collection

### Discovery Widgets
- **Trending** - Currently trending content
- **Popular** - Most popular content
- **Recommended** - Personalized recommendations (requires Trakt)
- **Anticipated** - Most anticipated upcoming content
- **Most Watched** - Most watched content

## Customization

### Themes
- Go to Settings → General → Theme
- Available themes: Default, Dark, Light

### Visual Options
- Show fanart backgrounds (Settings → General → Show fanart backgrounds)
- Animate widgets (Settings → General → Animate widgets)
- Widget refresh interval (Settings → Widgets → Widget refresh interval)

## Navigation

### Main Menu
- **Home** - Your personalized home screen with widgets
- **Movies** - Browse movies from AIOStreams
- **TV Shows** - Browse TV shows from AIOStreams
- **Search** - Search for content
- **Settings** - Configure the skin and AIOStreams

### Keyboard Shortcuts
- **Backspace** - Go back
- **Escape** - Close dialog/Return to home
- **I** - Show information dialog
- **C** - Open context menu

## Troubleshooting

### Widgets not showing content
1. Ensure AIOStreams addon is installed and working
2. Check that you're authorized with Trakt (for Trakt widgets)
3. Try resetting widgets to defaults
4. Check AIOStreams settings and network connection

### Skin not loading
1. Ensure Kodi version is 19 (Matrix) or higher
2. Check that AIOStreams addon is installed
3. Try reinstalling the skin
4. Check Kodi logs for errors

### Slow performance
1. Reduce number of active widgets
2. Increase widget refresh interval
3. Disable widget animations
4. Check your network connection speed

## Development

### File Structure
```
skin.aiodi/
├── addon.xml              # Skin metadata
├── service.py             # Background service
├── settings.xml           # Skin settings
├── 1080i/                 # Skin files (1080p)
│   ├── Home.xml          # Home screen
│   ├── Custom_AIOStreams_Config.xml  # Widget configurator
│   ├── includes/         # Reusable components
│   │   ├── Widgets.xml
│   │   └── AIOStreamsMenus.xml
│   ├── Defaults.xml      # Default control styles
│   └── includes.xml      # Main includes file
├── scripts/              # Helper scripts
│   └── widget_manager.py # Widget management service
├── colors/               # Color schemes
├── fonts/                # Font definitions
├── media/                # Images and assets
└── language/             # Localization files
```

### Widget Manager API

The widget manager can be called from XML using:
```xml
<onload>RunScript(special://skin/scripts/widget_manager.py,action=update,page=home)</onload>
```

Available actions:
- `update` - Update widget properties for a page
- `load` - Load all widget configurations
- `add` - Add a widget to a page
- `remove` - Remove a widget from a page
- `move_up` - Move widget up in order
- `move_down` - Move widget down in order
- `reset` - Reset widgets to defaults

## Contributing

Contributions are welcome! If you'd like to improve the skin:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Credits

- **Created by**: shiggsy365
- **Based on**: AIOStreams addon
- **Inspired by**: Modern streaming interfaces (Netflix, Plex, etc.)

## License

Creative Commons Attribution Non-Commercial Share-Alike 4.0

## Support

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/shiggsy365/AIOStreamsKODI/issues
- AIOStreams Discord: [Link if available]

## Changelog

### Version 1.0.0 (Initial Release)
- Dynamic widget system with visual configurator
- Deep AIOStreams integration
- Netflix-style interface
- Trakt integration for watchlists and progress
- Customizable home, movies, and shows pages
- Background service for automatic updates
- 15+ widget types available
- Theme support (Default, Dark, Light)

---

**Enjoy your personalized streaming experience with AIODI! 🎬**
