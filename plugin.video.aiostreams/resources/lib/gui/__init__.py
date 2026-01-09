# -*- coding: utf-8 -*-
"""
GUI module for AIOStreams addon.
Provides custom dialogs and windows independent of the user's Kodi skin.
"""
from .windows import (
    MultiLineSourceSelect,
    ProgrammaticMultiLineSelect,
    show_source_select_dialog
)

__all__ = [
    'MultiLineSourceSelect',
    'ProgrammaticMultiLineSelect',
    'show_source_select_dialog'
]
