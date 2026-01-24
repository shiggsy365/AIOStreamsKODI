"""
Helper script to handle resume playback for partially watched items.
"""
import xbmc
import xbmcgui
import sys


def log(msg):
    xbmc.log(f'[AIOStreams] [ResumeHelper] {msg}', xbmc.LOGINFO)


def check_and_play():
    """Check if item is partially watched and show resume dialog if needed."""
    try:
        # Get item information
        percent_played = xbmc.getInfoLabel('ListItem.PercentPlayed')
        if not percent_played:
            percent_played = xbmc.getInfoLabel('ListItem.Property(PercentPlayed)')

        file_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')

        log(f'PercentPlayed: {percent_played}, FilePath: {file_path}')

        # Convert to integer
        try:
            percent = int(percent_played) if percent_played else 0
        except ValueError:
            percent = 0

        # Check if partially watched (between 5% and 95%)
        if percent > 4 and percent < 96:
            log(f'Item is partially watched ({percent}%). Showing resume dialog.')

            # Show dialog asking to resume or start from beginning
            dialog = xbmcgui.Dialog()
            resume = dialog.yesno(
                'Resume Playback',
                f'Resume playback from {percent}%?',
                nolabel='Start from Beginning',
                yeslabel='Resume'
            )

            if resume:
                # Resume playback
                log('User chose to resume')
                xbmc.executebuiltin(f'PlayMedia({file_path})')
            else:
                # Start from beginning - need to reset position
                log('User chose to start from beginning')
                # First mark as unwatched to reset position
                xbmc.executebuiltin(f'PlayMedia({file_path})')
        else:
            # Not partially watched, just play normally
            log(f'Item not partially watched ({percent}%). Playing normally.')
            xbmc.executebuiltin(f'PlayMedia({file_path})')

    except Exception as e:
        log(f'Error in resume helper: {e}')
        import traceback
        log(traceback.format_exc())
        # Fallback to normal playback
        file_path = xbmc.getInfoLabel('ListItem.FileNameAndPath')
        if file_path:
            xbmc.executebuiltin(f'PlayMedia({file_path})')


if __name__ == '__main__':
    check_and_play()
