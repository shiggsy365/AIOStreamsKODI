# -*- coding: utf-8 -*-
"""Content filtering for AIOStreams"""
import xbmcaddon

ADDON = xbmcaddon.Addon()

# Genre filter mapping
GENRES = [
    'action', 'adventure', 'animation', 'anime', 'comedy', 'crime', 
    'documentary', 'drama', 'family', 'fantasy', 'history', 'horror',
    'music', 'mystery', 'romance', 'science-fiction', 'thriller', 
    'war', 'western'
]

# Rating filter mapping
RATINGS = ['g', 'pg', 'pg-13', 'r', 'nc-17', 'tv-y', 'tv-y7', 'tv-g', 'tv-pg', 'tv-14', 'tv-ma']


def is_genre_filtered():
    """Check if genre filtering is enabled."""
    return ADDON.getSetting('filter_genres_enabled') == 'true'


def is_rating_filtered():
    """Check if rating filtering is enabled."""
    return False  # Rating filters disabled


def get_filtered_genres():
    """Get list of genres to filter out."""
    if not is_genre_filtered():
        return []
    
    filtered = []
    for genre in GENRES:
        setting_key = f'filter_genre_{genre.replace("-", "_")}'
        if ADDON.getSetting(setting_key) == 'true':
            filtered.append(genre.lower())
    
    return filtered


def get_filtered_ratings():
    """Get list of ratings to filter out."""
    if not is_rating_filtered():
        return []
    
    filtered = []
    for rating in RATINGS:
        setting_key = f'filter_rating_{rating.replace("-", "_")}'
        if ADDON.getSetting(setting_key) == 'true':
            filtered.append(rating.upper())
    
    return filtered


def should_filter_item(meta):
    """
    Check if an item should be filtered based on genre and rating.
    
    Args:
        meta: Metadata dictionary with 'genres' and 'certification'/'rating' fields
    
    Returns:
        True if item should be filtered out, False otherwise
    """
    # Check genre filter
    if is_genre_filtered():
        filtered_genres = get_filtered_genres()
        item_genres = meta.get('genres', [])
        
        # Convert to lowercase for comparison
        item_genres_lower = [g.lower() for g in item_genres]
        
        # Filter if any genre matches
        for genre in filtered_genres:
            if genre in item_genres_lower:
                return True
    
    # Check rating filter
    if is_rating_filtered():
        filtered_ratings = get_filtered_ratings()
        item_rating = meta.get('certification', meta.get('rating', ''))
        
        # Handle both string and dict rating
        if isinstance(item_rating, dict):
            item_rating = ''
        
        item_rating = str(item_rating).upper()
        
        # Filter if rating matches
        if item_rating in filtered_ratings:
            return True
    
    return False


def filter_items(items):
    """
    Filter a list of items based on genre and rating settings.
    
    Args:
        items: List of metadata dictionaries
    
    Returns:
        Filtered list of items
    """
    if not is_genre_filtered() and not is_rating_filtered():
        return items
    
    return [item for item in items if not should_filter_item(item)]
