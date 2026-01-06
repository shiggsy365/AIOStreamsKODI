# Phase 4 Implementation: Background Service & Database Migration

## Overview
This document describes the Phase 4 implementation that adds automatic Trakt synchronization via a background service and database migration capabilities.

## Components

### 1. Background Service (`service.py`)

The background service runs automatically when Kodi starts and handles periodic Trakt synchronization.

#### Features:
- **Automatic Sync**: Syncs Trakt data every 5 minutes (configurable via settings)
- **Wake Sync**: Triggers sync when device wakes from sleep/screensaver
- **Settings Monitor**: Responds to addon settings changes
- **Startup Migration**: Checks and runs database migration on first startup

#### Key Classes:
- `AIOStreamsService`: Main service class that manages the sync loop
- `AIOStreamsMonitor`: Kodi monitor for system events (settings, wake)

#### Service Lifecycle:
1. Service starts on Kodi login
2. Runs migration check on first startup
3. Enters main loop checking for sync conditions every 30 seconds
4. Performs sync every 5 minutes if auto-sync is enabled
5. Responds to wake events and settings changes
6. Gracefully stops when Kodi shuts down

### 2. Database Migration (`resources/lib/database/migration.py`)

Handles migration from JSON cache to SQLite database for Trakt data.

#### Features:
- **One-time Execution**: Creates `.migration_complete` flag after first run
- **Safe Operation**: Checks for existing data before attempting migration
- **Graceful Handling**: Recognizes that old system didn't persistently cache Trakt data

#### Migration Process:
1. Check if migration flag exists (skip if present)
2. Check for JSON cache files
3. Attempt to migrate watchlist, watched status, and playback progress
4. Mark migration as complete
5. Log results

**Note**: In practice, the old implementation fetched Trakt data from the API on demand and didn't persistently store it in JSON files. The migration primarily serves to create the flag file and log the transition.

### 3. Database Maintenance Functions (`addon.py`)

Five new maintenance functions for managing the Trakt SQLite database:

#### `clear_trakt_database()`
- Clears all Trakt data from the local database
- Prompts user for confirmation
- Clears: shows, episodes, movies, watchlist, bookmarks, hidden items
- Preserves activities sync timestamps

#### `rebuild_trakt_database()`
- Clears database AND forces a fresh sync
- Two-step process:
  1. Clear all data including activities
  2. Force immediate sync via `force_trakt_sync()`
- Useful for recovering from data corruption

#### `show_database_info()`
- Displays statistics about the database:
  - Number of shows, episodes, movies
  - Number of watchlist items
  - Last sync timestamp
  - Database file size in KB
- Helpful for troubleshooting and monitoring

#### `vacuum_database()`
- Runs SQLite VACUUM command
- Optimizes database by:
  - Reclaiming unused space
  - Defragmenting the database file
  - Improving query performance

#### `force_trakt_sync()` (existing)
- Forces immediate Trakt sync
- Shows progress dialog
- Subject to 5-minute throttle

### 4. Settings Integration (`resources/settings.xml`)

New Trakt settings section with database maintenance options:

```xml
<setting id="trakt_sync_auto" type="bool" label="Enable Auto-Sync (Background Service)" default="true"/>
<setting id="trakt_sync_manual" type="action" label="Force Sync Now" action="..."/>

<setting id="trakt_database_info" type="action" label="Show Database Info" action="..."/>
<setting id="trakt_database_clear" type="action" label="Clear Trakt Database" action="..."/>
<setting id="trakt_database_rebuild" type="action" label="Rebuild Trakt Database" action="..."/>
<setting id="trakt_database_vacuum" type="action" label="Optimize Database (Vacuum)" action="..."/>
```

### 5. Service Registration (`addon.xml`)

Service is registered to start on Kodi login:

```xml
<extension point="xbmc.service" library="service.py" start="login" />
```

## Data Flow

### Auto-Sync Flow:
```
Kodi Startup
    ↓
Service Starts → Migration Check
    ↓
Main Loop (30s intervals)
    ↓
Check Auto-Sync Setting
    ↓
Check Trakt Authorization
    ↓
Check Time Since Last Sync (5 min threshold)
    ↓
Perform Sync (via TraktSyncDatabase.sync_activities())
    ↓
Update last_sync timestamp
    ↓
Loop continues
```

### Wake Sync Flow:
```
Screensaver Deactivates
    ↓
Monitor.onScreensaverDeactivated()
    ↓
Service.sync_on_wake()
    ↓
Check Auto-Sync Setting
    ↓
Perform Sync (bypass time check)
```

### Settings Change Flow:
```
User Changes Settings
    ↓
Monitor.onSettingsChanged()
    ↓
Service.reload_settings()
    ↓
Re-read trakt_sync_auto setting
    ↓
Apply new configuration
```

## Database Schema

The service uses the existing TraktSyncDatabase schema:

- **shows**: TV show metadata and watch progress
- **episodes**: Episode metadata and watch status
- **movies**: Movie metadata and watch status
- **watchlist**: Watchlist items (movies and shows)
- **activities**: Sync timestamps for delta sync
- **bookmarks**: Playback progress/resume points
- **hidden**: Hidden items (for Next Up filtering)

## Configuration

### Enable/Disable Auto-Sync:
Settings → Trakt → Enable Auto-Sync (Background Service)

### Sync Interval:
Hardcoded to 5 minutes (can be modified in `service.py`)

### Manual Operations:
Settings → Trakt → Database Maintenance section

## Logging

All service operations are logged with appropriate levels:

- `LOGINFO`: Service lifecycle, sync operations
- `LOGDEBUG`: Detailed sync info, settings changes
- `LOGWARNING`: Sync errors, throttling
- `LOGERROR`: Critical failures

Search logs for `[AIOStreams Service]` or `[AIOStreams]`

## Troubleshooting

### Service Not Starting
1. Check Kodi log for service errors
2. Verify addon.xml has service extension
3. Restart Kodi

### Auto-Sync Not Working
1. Check "Enable Auto-Sync" is enabled in settings
2. Verify Trakt is authorized (trakt_token present)
3. Check if sync is throttled (5 min minimum)
4. View logs for sync attempts

### Database Issues
1. Use "Show Database Info" to check state
2. Try "Optimize Database (Vacuum)"
3. If corrupted, use "Rebuild Trakt Database"
4. Check file permissions on database file

### Migration Issues
1. Check for `.migration_complete` flag in addon_data
2. Delete flag to re-run migration
3. Check logs for migration errors

## Performance Considerations

- Service runs in background with minimal CPU usage
- Sync is throttled to 5 minutes minimum
- Database operations are optimized with indexes
- Migration is one-time operation

## Future Enhancements

Potential improvements for future versions:

1. Configurable sync interval in settings
2. Option to sync on library update
3. Selective sync (only watchlist, only watched, etc.)
4. Sync statistics and history
5. Conflict resolution for concurrent changes
6. Background notification for sync completion
7. Scheduled sync (e.g., daily at specific time)

## Testing

To test the implementation:

1. **Install addon** - Service should start automatically
2. **Check logs** - Verify service startup message
3. **Enable auto-sync** - Settings → Trakt → Enable Auto-Sync
4. **Wait 5 minutes** - Check for automatic sync in logs
5. **Test wake sync** - Activate/deactivate screensaver
6. **Test maintenance** - Use each database maintenance button
7. **Verify data** - Check Show Database Info for counts

## Version History

- **v2.8.0** - Initial Phase 4 implementation with background service, migration, and maintenance tools
