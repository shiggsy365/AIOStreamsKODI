# Custom Kodi Skin: AIOStreams Fentastic Edition

## Project Overview

Create a custom Kodi skin based on Fentastic (by ivarbrandt) with deep AIOStreams integration as a service.

## Core Concept

**Name Ideas:**
- `skin.fentastic.aiostreams`
- `skin.aiostreams.fentastic`
- `skin.streamtastic`

**Philosophy:**
- AIOStreams is the primary content source
- Clean, Netflix-style interface
- Widget-based home with drag-and-drop configuration
- No need to "open addon" - content is native to skin

## Architecture

### 1. Skin Structure
```
skin.fentastic.aiostreams/
├── addon.xml                    # Skin metadata
├── 1080i/                       # Skin files (1080p)
│   ├── Home.xml                # Main home screen
│   ├── MyVideoNav.xml          # Video library view
│   ├── MovieInformation.xml    # Movie info dialog
│   ├── TVShowInformation.xml   # Show info dialog
│   ├── Custom_AIOStreams_Config.xml  # Widget configurator
│   ├── includes/               # Reusable components
│   │   ├── Widgets.xml        # Widget definitions
│   │   └── AIOStreamsMenus.xml # AIOStreams integration
│   └── ...
├── colors/                     # Color schemes
├── fonts/                      # Font definitions
├── media/                      # Images, icons, backgrounds
└── scripts/                    # Helper scripts
    └── widget_manager.py       # Widget configuration service
```

### 2. AIOStreams Integration Methods

**Option A: Service Integration (Recommended)**
- AIOStreams runs as background service
- Skin calls it via JSON-RPC or window properties
- Widget content updates automatically
- No need to navigate through addon

**Option B: Deep Linking**
- Skin directly calls AIOStreams plugin URLs
- `plugin://plugin.video.aiostreams/?action=...`
- Simpler but less integrated feel

**Option C: Hybrid**
- AIOStreams provides service for metadata
- Skin uses direct plugin calls for actions
- Best of both worlds

## Features

### Default Tabs

**Home:**
- Continue Watching (AIOStreams Trakt)
- Trending Movies
- Trending TV Shows
- Your Watchlist
- Recommended for You
- Recently Added

**Movies:**
- All Movies
- Trending
- Popular
- By Genre (Action, Comedy, Drama, etc.)
- Watchlist
- Collection

**Shows:**
- All Shows
- Continue Watching
- Next Up
- Trending
- Popular
- By Genre
- Watchlist
- Collection

**Live TV:**
- Live channels (if AIOStreams supports)
- Or integrate with PVR backend
- Or hide if not used

### Widget Configuration System

**Visual Configurator:**
```
┌─────────────────────────────────────────┐
│  Widget Configuration                   │
├─────────────────────────────────────────┤
│                                         │
│  Available Widgets:                     │
│  ☐ Continue Watching                   │
│  ☐ Trending Movies                     │
│  ☐ Trending TV Shows                   │
│  ☐ Popular Movies                      │
│  ☐ Popular TV Shows                    │
│  ☐ Watchlist - Movies                  │
│  ☐ Watchlist - Shows                   │
│  ☐ Recommended Movies                  │
│  ☐ Recommended Shows                   │
│  ☐ Collection - Movies                 │
│  ☐ Collection - Shows                  │
│  ☐ Genre: Action                       │
│  ☐ Genre: Comedy                       │
│  ☐ [Custom AIOStreams Catalog...]      │
│                                         │
│  Current Page: [Home ▼]                │
│                                         │
│  Active Widgets (Drag to Reorder):     │
│  1. Continue Watching          [↑][↓]  │
│  2. Trending Movies            [↑][↓]  │
│  3. Watchlist - Movies         [↑][↓]  │
│                                         │
│  [Add Widget] [Save] [Reset]           │
└─────────────────────────────────────────┘
```

**Implementation:**
- Settings stored in: `skin.settings`
- Format: JSON or XML
- Properties:
  - `home.widget.1.type = "continue_watching"`
  - `home.widget.1.label = "Continue Watching"`
  - `home.widget.1.action = "plugin://plugin.video.aiostreams/?action=trakt_continue_watching"`
  - `home.widget.2.type = "trending_movies"`
  - etc.

## Technical Implementation

### Step 1: Fork Fentastic Skin

```bash
git clone https://github.com/ivarbrandt/skin.fentastic
cd skin.fentastic
```

### Step 2: Modify addon.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<addon id="skin.fentastic.aiostreams" version="1.0.0" name="Fentastic AIOStreams" provider-name="Jon">
    <requires>
        <import addon="xbmc.gui" version="5.16.0"/>
        <import addon="plugin.video.aiostreams" version="1.5.0"/>
        <import addon="script.skinshortcuts" version="1.0.0"/>
    </requires>
    <extension point="xbmc.gui.skin" debugging="false">
        <res width="1920" height="1080" aspect="16:9" default="true" folder="1080i" />
    </extension>
    <extension point="xbmc.service" library="service.py">
        <provides>service</provides>
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary lang="en_GB">Fentastic skin with deep AIOStreams integration</summary>
        <description lang="en_GB">A custom skin based on Fentastic, designed specifically for AIOStreams with built-in widget management and configuration.</description>
        <platform>all</platform>
        <license>Creative Commons Attribution Non-Commercial Share-Alike 4.0</license>
    </extension>
</addon>
```

### Step 3: Create Widget System

**File: `scripts/widget_manager.py`**

```python
import xbmc
import xbmcaddon
import xbmcgui
import json

ADDON = xbmcaddon.Addon()

class WidgetManager:
    """Manage AIOStreams widgets for skin."""
    
    AVAILABLE_WIDGETS = {
        'continue_watching': {
            'label': 'Continue Watching',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_continue_watching',
            'icon': 'DefaultTVShows.png'
        },
        'next_up': {
            'label': 'Next Up',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_next_up',
            'icon': 'DefaultTVShows.png'
        },
        'trending_movies': {
            'label': 'Trending Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_trending&media_type=movies',
            'icon': 'DefaultMovies.png'
        },
        'trending_shows': {
            'label': 'Trending TV Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_trending&media_type=shows',
            'icon': 'DefaultTVShows.png'
        },
        'popular_movies': {
            'label': 'Popular Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_popular&media_type=movies',
            'icon': 'DefaultMovies.png'
        },
        'popular_shows': {
            'label': 'Popular TV Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_popular&media_type=shows',
            'icon': 'DefaultTVShows.png'
        },
        'watchlist_movies': {
            'label': 'Watchlist - Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=movies',
            'icon': 'DefaultMovies.png'
        },
        'watchlist_shows': {
            'label': 'Watchlist - Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=shows',
            'icon': 'DefaultTVShows.png'
        },
        'recommended_movies': {
            'label': 'Recommended Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_recommended&media_type=movies',
            'icon': 'DefaultMovies.png'
        },
        'recommended_shows': {
            'label': 'Recommended Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_recommended&media_type=shows',
            'icon': 'DefaultTVShows.png'
        },
        'collection_movies': {
            'label': 'Collection - Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_collection&media_type=movies',
            'icon': 'DefaultMovies.png'
        },
        'collection_shows': {
            'label': 'Collection - Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_collection&media_type=shows',
            'icon': 'DefaultTVShows.png'
        }
    }
    
    def get_page_widgets(self, page):
        """Get active widgets for a page."""
        setting_key = f'{page}_widgets'
        widgets_json = ADDON.getSetting(setting_key)
        
        if widgets_json:
            return json.loads(widgets_json)
        
        # Return defaults
        if page == 'home':
            return ['continue_watching', 'trending_movies', 'trending_shows', 'watchlist_movies']
        elif page == 'movies':
            return ['trending_movies', 'popular_movies', 'watchlist_movies', 'collection_movies']
        elif page == 'shows':
            return ['continue_watching', 'next_up', 'trending_shows', 'watchlist_shows']
        
        return []
    
    def save_page_widgets(self, page, widgets):
        """Save widget configuration for a page."""
        setting_key = f'{page}_widgets'
        ADDON.setSetting(setting_key, json.dumps(widgets))
    
    def set_window_properties(self, page):
        """Set window properties for skin to use."""
        window = xbmcgui.Window(10000)  # Home window
        widgets = self.get_page_widgets(page)
        
        # Clear existing properties
        for i in range(20):
            window.clearProperty(f'AIOStreams.{page}.Widget.{i}.Label')
            window.clearProperty(f'AIOStreams.{page}.Widget.{i}.Action')
            window.clearProperty(f'AIOStreams.{page}.Widget.{i}.Icon')
        
        # Set new properties
        for i, widget_id in enumerate(widgets):
            if widget_id in self.AVAILABLE_WIDGETS:
                widget = self.AVAILABLE_WIDGETS[widget_id]
                window.setProperty(f'AIOStreams.{page}.Widget.{i}.Label', widget['label'])
                window.setProperty(f'AIOStreams.{page}.Widget.{i}.Action', widget['action'])
                window.setProperty(f'AIOStreams.{page}.Widget.{i}.Icon', widget['icon'])
        
        window.setProperty(f'AIOStreams.{page}.Widget.Count', str(len(widgets)))
```

### Step 4: Create Widget Configurator Window

**File: `1080i/Custom_AIOStreams_Config.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<window type="window" id="1150">
    <defaultcontrol always="true">100</defaultcontrol>
    <onload>RunScript(special://skin/scripts/widget_manager.py,action=load)</onload>
    <controls>
        <!-- Background -->
        <control type="image">
            <width>1920</width>
            <height>1080</height>
            <texture>dialogs/dialog-bg.png</texture>
        </control>
        
        <!-- Title -->
        <control type="label">
            <left>90</left>
            <top>60</top>
            <width>1740</width>
            <height>60</height>
            <font>font37_title</font>
            <textcolor>white</textcolor>
            <label>AIOStreams Widget Configuration</label>
        </control>
        
        <!-- Page Selector -->
        <control type="radiobutton" id="200">
            <left>90</left>
            <top>150</top>
            <width>400</width>
            <height>50</height>
            <font>font30</font>
            <label>Page: Home</label>
            <onclick>RunScript(special://skin/scripts/widget_manager.py,action=switch_page,page=home)</onclick>
        </control>
        
        <!-- Available Widgets List -->
        <control type="label">
            <left>90</left>
            <top>250</top>
            <width>800</width>
            <height>40</height>
            <font>font27</font>
            <label>Available Widgets</label>
        </control>
        
        <control type="list" id="100">
            <left>90</left>
            <top>300</top>
            <width>800</width>
            <height>600</height>
            <onright>300</onright>
            <itemlayout height="60">
                <control type="label">
                    <width>800</width>
                    <height>60</height>
                    <font>font27</font>
                    <textcolor>grey</textcolor>
                    <label>$INFO[ListItem.Label]</label>
                </control>
            </itemlayout>
            <focusedlayout height="60">
                <control type="image">
                    <width>800</width>
                    <height>60</height>
                    <texture colordiffuse="highlight">common/white.png</texture>
                </control>
                <control type="label">
                    <width>800</width>
                    <height>60</height>
                    <font>font27</font>
                    <textcolor>white</textcolor>
                    <label>$INFO[ListItem.Label]</label>
                </control>
            </focusedlayout>
            <content>
                <item>
                    <label>Continue Watching</label>
                    <property name="widget_id">continue_watching</property>
                </item>
                <item>
                    <label>Trending Movies</label>
                    <property name="widget_id">trending_movies</property>
                </item>
                <!-- More widgets... -->
            </content>
        </control>
        
        <!-- Active Widgets List -->
        <control type="label">
            <left>1030</left>
            <top>250</top>
            <width>800</width>
            <height>40</height>
            <font>font27</font>
            <label>Active Widgets (Ordered)</label>
        </control>
        
        <control type="list" id="300">
            <left>1030</left>
            <top>300</top>
            <width>800</width>
            <height>600</height>
            <onleft>100</onleft>
            <!-- Active widgets loaded dynamically -->
        </control>
        
        <!-- Buttons -->
        <control type="button" id="400">
            <left>90</left>
            <top>950</top>
            <width>200</width>
            <height>60</height>
            <font>font27</font>
            <label>Add Widget</label>
            <onclick>RunScript(special://skin/scripts/widget_manager.py,action=add)</onclick>
        </control>
        
        <control type="button" id="500">
            <left>320</left>
            <top>950</top>
            <width>200</width>
            <height>60</height>
            <font>font27</font>
            <label>Save</label>
            <onclick>RunScript(special://skin/scripts/widget_manager.py,action=save)</onclick>
        </control>
    </controls>
</window>
```

### Step 5: Integrate Widgets into Home.xml

**File: `1080i/Home.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<window>
    <onload>RunScript(special://skin/scripts/widget_manager.py,action=update,page=home)</onload>
    <controls>
        <!-- Widget 1 -->
        <control type="group">
            <visible>!String.IsEmpty(Window(Home).Property(AIOStreams.home.Widget.0.Label))</visible>
            <control type="label">
                <label>$INFO[Window(Home).Property(AIOStreams.home.Widget.0.Label)]</label>
            </control>
            <control type="list">
                <content target="video">
                    <path>$INFO[Window(Home).Property(AIOStreams.home.Widget.0.Action)]</path>
                </content>
            </control>
        </control>
        
        <!-- Widget 2 -->
        <control type="group">
            <visible>!String.IsEmpty(Window(Home).Property(AIOStreams.home.Widget.1.Label))</visible>
            <!-- Same structure... -->
        </control>
        
        <!-- Repeat for all widgets... -->
    </controls>
</window>
```

## Benefits

### For Users:
- **No addon navigation**: Content is native to skin
- **Customizable**: Drag-drop widgets per page
- **Fast**: AIOStreams service keeps content fresh
- **Clean**: One unified interface

### For You:
- **Control**: Complete control over UX
- **Branding**: Your streaming platform
- **Integration**: Deep AIOStreams + Trakt integration
- **Extensibility**: Easy to add new widgets

## Next Steps

1. **Clone Fentastic**: Fork the base skin
2. **Study Structure**: Understand Fentastic's layout
3. **Create Widget Manager**: Python service for configuration
4. **Build Configurator UI**: Custom XML window
5. **Integrate Home.xml**: Dynamic widget loading
6. **Test**: Verify widgets load correctly
7. **Polish**: Add animations, transitions
8. **Package**: Create skin.fentastic.aiostreams.zip

## Challenges

**1. Kodi Skin Limitations:**
- Can't create complex UI in XML alone
- Need Python service for dynamic content
- Window properties have limits

**Solution**: Hybrid approach with service + XML

**2. AIOStreams as Dependency:**
- Users must install AIOStreams addon
- Skin should gracefully handle missing addon

**Solution**: Check addon presence, show setup wizard

**3. Widget Performance:**
- Too many widgets = slow loading
- Need smart caching

**Solution**: Limit active widgets, use AIOStreams cache

## Timeline Estimate

- **Week 1**: Setup, study Fentastic, plan structure
- **Week 2**: Widget manager service
- **Week 3**: Configurator UI
- **Week 4**: Home/Movies/Shows integration
- **Week 5**: Polish, testing, packaging

## Would You Like Me To:

1. **Start Building**: Create the initial skin structure
2. **Widget Manager First**: Build Python service
3. **Configurator UI**: Create the visual editor
4. **Full Package**: All of the above

Let me know and I'll start creating files!
