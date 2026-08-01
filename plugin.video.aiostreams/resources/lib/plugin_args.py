"""Pure parsing helpers for Kodi plugin invocation arguments."""
from urllib.parse import parse_qsl


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
