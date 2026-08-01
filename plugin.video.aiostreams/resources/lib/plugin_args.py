"""Pure parsing helpers for Kodi plugin invocation arguments."""
from urllib.parse import parse_qsl, unquote_plus


def parse_plugin_params(arg_raw):
    """Parse a Kodi plugin query string or clean navigation path."""
    if arg_raw.startswith('?'):
        return dict(parse_qsl(arg_raw[1:]))

    if '/' not in arg_raw:
        return {}

    parts = [part for part in arg_raw.split('/') if part]
    params = {}
    if len(parts) >= 1:
        params['action'] = parts[0]
    if len(parts) >= 2:
        params['meta_id'] = parts[1]
    if len(parts) >= 3:
        params['season'] = parts[2]
    return params


def parse_search_query(args):
    """Extract a Global Search term from common Kodi script argument forms."""
    for arg in args:
        if not arg:
            continue
        query_string = arg[1:] if arg.startswith('?') else arg
        params = dict(parse_qsl(query_string))
        for key in ('query', 'search', 'q'):
            if params.get(key):
                return params[key]

    # Some Global Search versions pass the term as a positional argument rather
    # than a plugin-style query string.
    for arg in args:
        if arg and not arg.startswith('?') and '=' not in arg:
            return unquote_plus(arg)
    return ''
