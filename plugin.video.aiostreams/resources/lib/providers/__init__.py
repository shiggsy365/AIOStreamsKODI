# -*- coding: utf-8 -*-
"""
Provider abstraction layer for AIOStreams addon.
Enables modular, extensible provider system based on Seren's patterns.
"""
from .base import BaseProvider, ProviderManager
from .aiostreams import AIOStreamsProvider

__all__ = ['BaseProvider', 'ProviderManager', 'AIOStreamsProvider']
