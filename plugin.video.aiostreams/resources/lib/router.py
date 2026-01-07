# -*- coding: utf-8 -*-
"""
Action router for AIOStreams addon.
Uses registry pattern instead of if/elif chains for cleaner code.
Based on Seren's dispatch patterns.
"""
import xbmc
import xbmcplugin


class ActionRegistry:
    """
    Registry for plugin actions with support for:
    - Default action handlers
    - Action metadata (requires_auth, etc.)
    - Pre/post action hooks
    """

    def __init__(self):
        """Initialize action registry."""
        self._actions = {}
        self._default_action = None
        self._pre_hooks = []
        self._post_hooks = []

    def register(self, action_name, handler, requires_auth=False, description=None):
        """
        Register an action handler.

        Args:
            action_name: Name of the action
            handler: Function to call for this action
            requires_auth: Whether this action requires Trakt auth
            description: Optional description for debugging
        """
        self._actions[action_name] = {
            'handler': handler,
            'requires_auth': requires_auth,
            'description': description or action_name
        }

    def register_default(self, handler):
        """
        Register the default action handler (when no action specified).

        Args:
            handler: Function to call as default
        """
        self._default_action = handler

    def register_pre_hook(self, hook):
        """
        Register a pre-action hook (called before every action).

        Args:
            hook: Function to call before action (receives action_name, params)
                  Return False to cancel action execution
        """
        self._pre_hooks.append(hook)

    def register_post_hook(self, hook):
        """
        Register a post-action hook (called after every action).

        Args:
            hook: Function to call after action (receives action_name, params, result)
        """
        self._post_hooks.append(hook)

    def action(self, action_name, requires_auth=False, description=None):
        """
        Decorator for registering action handlers.

        Usage:
            @router.action('search')
            def search(params):
                ...
        """
        def decorator(func):
            self.register(action_name, func, requires_auth, description)
            return func
        return decorator

    def dispatch(self, params, handle=None):
        """
        Dispatch to the appropriate action handler.

        Args:
            params: Dictionary of request parameters
            handle: Plugin handle for directory operations

        Returns:
            Result from action handler
        """
        action = params.get('action', '')

        # Run pre-hooks
        for hook in self._pre_hooks:
            try:
                if hook(action, params) is False:
                    xbmc.log(f'[AIOStreams] Pre-hook cancelled action: {action}', xbmc.LOGDEBUG)
                    return None
            except Exception as e:
                xbmc.log(f'[AIOStreams] Pre-hook error: {e}', xbmc.LOGERROR)

        # Get action info
        action_info = self._actions.get(action)

        # No action or unknown action - use default
        if not action or action_info is None:
            if self._default_action:
                xbmc.log(f'[AIOStreams] Dispatching to default action', xbmc.LOGDEBUG)
                result = self._default_action(params)
            else:
                xbmc.log(f'[AIOStreams] Unknown action with no default: {action}', xbmc.LOGWARNING)
                result = None
        else:
            # Check auth requirement
            if action_info['requires_auth']:
                try:
                    from . import trakt
                    if not trakt.is_authenticated():
                        xbmc.log(f'[AIOStreams] Action requires auth: {action}', xbmc.LOGWARNING)
                        import xbmcgui
                        xbmcgui.Dialog().notification(
                            'AIOStreams',
                            'Please authenticate with Trakt first',
                            xbmcgui.NOTIFICATION_WARNING
                        )
                        return None
                except:
                    pass

            # Execute action
            xbmc.log(f'[AIOStreams] Dispatching action: {action}', xbmc.LOGDEBUG)
            try:
                result = action_info['handler'](params)
            except Exception as e:
                xbmc.log(f'[AIOStreams] Action error ({action}): {e}', xbmc.LOGERROR)
                result = None

        # Run post-hooks
        for hook in self._post_hooks:
            try:
                hook(action, params, result)
            except Exception as e:
                xbmc.log(f'[AIOStreams] Post-hook error: {e}', xbmc.LOGERROR)

        return result

    def get_action(self, action_name):
        """Get action info by name."""
        return self._actions.get(action_name)

    def list_actions(self):
        """List all registered actions."""
        return list(self._actions.keys())

    @property
    def action_count(self):
        """Get number of registered actions."""
        return len(self._actions)


# Global router instance
_router = None


def get_router():
    """Get global ActionRegistry instance."""
    global _router
    if _router is None:
        _router = ActionRegistry()
    return _router


def action(action_name, requires_auth=False, description=None):
    """
    Decorator for registering action handlers with global router.

    Usage:
        @action('search')
        def search(params):
            ...
    """
    return get_router().action(action_name, requires_auth, description)


def dispatch(params, handle=None):
    """Dispatch to action handler using global router."""
    return get_router().dispatch(params, handle)


def set_default(handler):
    """Set default action handler for global router."""
    get_router().register_default(handler)
