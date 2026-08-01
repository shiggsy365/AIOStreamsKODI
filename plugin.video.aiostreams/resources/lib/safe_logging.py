"""Helpers for logging operational context without exposing user data."""
import hashlib


def redact_identifier(value):
    """Return a stable, non-reversible marker suitable for log correlation."""
    if value is None or value == '':
        return '<missing>'
    digest = hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:12]
    return f'id:{digest}'


def error_name(error):
    """Return an exception class name without potentially sensitive details."""
    return type(error).__name__
