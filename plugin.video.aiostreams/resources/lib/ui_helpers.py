# -*- coding: utf-8 -*-
"""UI helper functions for AIOStreams addon"""
from . import constants
from . import settings_helpers


def format_progress_bar(percentage, width=10):
    """
    Create a visual progress bar.
    Example: [████████░░] 85%
    """
    if percentage < 0:
        percentage = 0
    if percentage > 100:
        percentage = 100

    filled = int((percentage / 100) * width)
    empty = width - filled

    bar = '█' * filled + '░' * empty
    return f"[{bar}] {percentage}%"


def get_watched_color(is_watched, in_progress=False):
    """Get color code based on watched status."""
    if not settings_helpers.get_color_code_items():
        return constants.COLOR_UNWATCHED

    if is_watched:
        return constants.COLOR_WATCHED
    elif in_progress:
        return constants.COLOR_IN_PROGRESS
    else:
        return constants.COLOR_UNWATCHED


def format_episode_title(episode_num, episode_title, is_watched=False, progress=0):
    """
    Format episode title with color coding and progress.
    Example: [COLOR blue]5. Episode Title[/COLOR] [████████░░] 85%
    """
    # Determine color
    in_progress = progress > 0 and progress < 100
    color = get_watched_color(is_watched, in_progress)

    # Base title
    formatted = f"[COLOR {color}]{episode_num}. {episode_title}[/COLOR]"

    # Add progress bar if enabled and in progress
    if settings_helpers.get_show_progress_bars() and in_progress:
        progress_bar = format_progress_bar(progress, width=10)
        formatted += f" {progress_bar}"

    return formatted


def format_season_title(season_num, episode_count, aired, completed):
    """
    Format season title with watch progress.
    Example: [COLOR blue]Season 1 (10 episodes)[/COLOR] [████████░░] 8/10
    """
    # Calculate progress
    if aired > 0:
        progress = int((completed / aired) * 100)
    else:
        progress = 0

    is_watched = aired > 0 and aired == completed
    in_progress = completed > 0 and completed < aired

    color = get_watched_color(is_watched, in_progress)

    # Base title
    formatted = f"[COLOR {color}]Season {season_num} ({episode_count} episodes)[/COLOR]"

    # Add progress if enabled
    if settings_helpers.get_show_progress_bars() and (in_progress or is_watched):
        if is_watched:
            formatted += " ✓"
        else:
            progress_bar = format_progress_bar(progress, width=8)
            formatted += f" {progress_bar} ({completed}/{aired})"

    return formatted


def format_movie_title(title, is_watched=False):
    """
    Format movie title with color coding.
    Example: [COLOR blue]Movie Title[/COLOR]
    """
    color = get_watched_color(is_watched, False)
    return f"[COLOR {color}]{title}[/COLOR]"


def format_show_title(title, aired, completed):
    """
    Format show title with watch progress.
    Example: [COLOR blue]Show Title[/COLOR] [████████░░] 45/50
    """
    if aired > 0:
        progress = int((completed / aired) * 100)
    else:
        progress = 0

    is_watched = aired > 0 and aired == completed
    in_progress = completed > 0 and completed < aired

    color = get_watched_color(is_watched, in_progress)

    formatted = f"[COLOR {color}]{title}[/COLOR]"

    # Add progress if enabled
    if settings_helpers.get_show_progress_bars() and (in_progress or is_watched):
        if is_watched:
            formatted += " ✓"
        else:
            progress_bar = format_progress_bar(progress, width=8)
            formatted += f" {progress_bar} ({completed}/{aired})"

    return formatted


def add_info_labels(list_item, meta, content_type):
    """Add additional info labels to list item for better UI."""
    info_tag = list_item.getVideoInfoTag()

    # Add IMDB rating badge if available
    rating_data = meta.get('rating', {})
    if isinstance(rating_data, dict):
        imdb_rating = rating_data.get('imdb')
        if imdb_rating:
            try:
                rating_float = float(imdb_rating)
                if rating_float >= 8.0:
                    info_tag.setUserRating(10)
                elif rating_float >= 7.0:
                    info_tag.setUserRating(8)
                elif rating_float >= 6.0:
                    info_tag.setUserRating(6)
            except:
                pass

    return list_item


def format_time_remaining(total_time, current_time):
    """
    Format remaining time for resume.
    Example: "45m remaining"
    """
    remaining = total_time - current_time

    if remaining <= 0:
        return "Finished"

    hours = remaining // 3600
    minutes = (remaining % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m remaining"
    else:
        return f"{minutes}m remaining"


def get_resume_label(percentage):
    """Get resume label for context menu."""
    if percentage > 0 and percentage < 100:
        return f"Resume from {percentage}%"
    else:
        return "Play from beginning"


def truncate_text(text, max_length=50):
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + '...'


def format_list_header(text, color='blue'):
    """Format a list header/category."""
    return f"[B][COLOR {color}]{text}[/COLOR][/B]"


def format_load_more(count=None):
    """Format 'Load More' list item."""
    if count:
        return f'[COLOR yellow]» Load More... ({count} more)[/COLOR]'
    else:
        return '[COLOR yellow]» Load More...[/COLOR]'
