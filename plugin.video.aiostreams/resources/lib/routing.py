"""Small, explicit dispatcher for parsed Kodi plugin actions."""


def normalize_params(params):
    """Return a copy with supported search-query aliases normalized."""
    params = dict(params or {})
    if not params.get('action') and any(key in params for key in ('search', 'query', 'q')):
        params['action'] = 'search'
    if not params.get('query'):
        for key in ('search', 'q'):
            if params.get(key):
                params['query'] = params[key]
                break
    return params


def dispatch(params, routes, default_handler, on_unknown=None, on_error=None):
    """Dispatch parsed parameters to one explicit handler table.

    Handlers receive the normalized parameter dictionary. ``on_unknown`` and
    ``on_error`` keep Kodi-specific logging at the add-on boundary.
    """
    params = normalize_params(params)
    action_name = params.get('action', '')
    handler = routes.get(action_name)
    if handler is None:
        if action_name and on_unknown:
            on_unknown(action_name)
        handler = default_handler
    try:
        return handler(params)
    except Exception as error:
        if on_error:
            on_error(action_name, error)
        return None
