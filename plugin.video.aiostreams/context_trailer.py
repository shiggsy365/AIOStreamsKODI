import xbmc

if __name__ == '__main__':
    # Try async property first (fresh from Info Window), then ListItem (cached)
    trailer_url = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.Trailer)')
    if not trailer_url:
        trailer_url = xbmc.getInfoLabel('ListItem.Trailer')
    if trailer_url:
        xbmc.executebuiltin(f'PlayMedia({trailer_url})')
    else:
        xbmc.executebuiltin('Notification(AIOStreams, No trailer available, 3000)')
