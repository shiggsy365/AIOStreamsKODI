# -*- coding: utf-8 -*-
"""
Network utilities for AIOStreams addon.
Includes retry logic, Android sleep handling, and request helpers.
Based on Seren's network patterns.
"""
import time
import platform
import functools
import requests
import xbmc
import xbmcgui


# Detect Android platform once at module load
_IS_ANDROID = None


def is_android():
    """
    Check if running on Android platform.

    Returns:
        bool: True if running on Android
    """
    global _IS_ANDROID
    if _IS_ANDROID is None:
        try:
            system = platform.system().lower()
            release = platform.release().lower()
            _IS_ANDROID = system == 'linux' and 'android' in release
        except:
            _IS_ANDROID = False
    return _IS_ANDROID


def retry_on_failure(max_retries=3, base_delay=1, exponential=True, exceptions=(requests.RequestException,)):
    """
    Decorator for retrying functions on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        exponential: If True, use exponential backoff (2^n * base_delay)
        exceptions: Tuple of exception types to catch and retry

    Usage:
        @retry_on_failure(max_retries=3, base_delay=2)
        def fetch_data(url):
            return requests.get(url)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        if exponential:
                            delay = base_delay * (2 ** attempt)
                        else:
                            delay = base_delay

                        xbmc.log(
                            f'[AIOStreams] {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), '
                            f'retrying in {delay}s: {e}',
                            xbmc.LOGWARNING
                        )
                        time.sleep(delay)
                    else:
                        xbmc.log(
                            f'[AIOStreams] {func.__name__} failed after {max_retries + 1} attempts: {e}',
                            xbmc.LOGERROR
                        )

            # Re-raise the last exception if all retries failed
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def retry_on_sleep(max_retries=3, sleep_check_delay=2):
    """
    Decorator for retrying functions when Android wakes from sleep.
    Includes sleep detection and network availability check.

    Args:
        max_retries: Maximum retry attempts for sleep-related failures
        sleep_check_delay: Seconds to wait between sleep checks

    Usage:
        @retry_on_sleep()
        def api_call():
            return requests.get('https://api.example.com/data')
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not is_android():
                # Not Android, just execute normally
                return func(*args, **kwargs)

            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.ConnectionError as e:
                    last_exception = e

                    if attempt < max_retries:
                        xbmc.log(
                            f'[AIOStreams] Connection error on Android (attempt {attempt + 1}), '
                            f'waiting for network...',
                            xbmc.LOGWARNING
                        )

                        # Wait for network to become available
                        if _wait_for_network(max_wait=sleep_check_delay * 2):
                            xbmc.log('[AIOStreams] Network restored, retrying...', xbmc.LOGINFO)
                        else:
                            time.sleep(sleep_check_delay)
                    else:
                        xbmc.log(
                            f'[AIOStreams] {func.__name__} failed after {max_retries + 1} attempts: {e}',
                            xbmc.LOGERROR
                        )

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def _wait_for_network(max_wait=10, check_url='https://api.trakt.tv'):
    """
    Wait for network to become available.

    Args:
        max_wait: Maximum seconds to wait
        check_url: URL to check for connectivity

    Returns:
        bool: True if network is available
    """
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            requests.head(check_url, timeout=2)
            return True
        except:
            time.sleep(1)

    return False


def make_request(url, method='GET', headers=None, data=None, json_data=None,
                 timeout=10, error_message='Request failed', notify_errors=True,
                 return_response=False):
    """
    Make an HTTP request with standardized error handling.

    Args:
        url: URL to request
        method: HTTP method (GET, POST, etc.)
        headers: Request headers dict
        data: Form data for POST requests
        json_data: JSON data for POST requests
        timeout: Request timeout in seconds
        error_message: Error message to display on failure
        notify_errors: If True, show notification on error
        return_response: If True, return full response object instead of JSON

    Returns:
        JSON response data, response object, or None on error
    """
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            json=json_data,
            timeout=timeout
        )

        if return_response:
            return response

        response.raise_for_status()
        return response.json()

    except requests.Timeout:
        if notify_errors:
            xbmcgui.Dialog().notification('AIOStreams', 'Request timed out', xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f'[AIOStreams] Request timeout: {url}', xbmc.LOGERROR)
        return None

    except requests.HTTPError as e:
        if notify_errors:
            xbmcgui.Dialog().notification('AIOStreams', f'{error_message}', xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f'[AIOStreams] HTTP error: {e}', xbmc.LOGERROR)
        return None

    except requests.RequestException as e:
        if notify_errors:
            xbmcgui.Dialog().notification('AIOStreams', f'{error_message}', xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f'[AIOStreams] Request error: {e}', xbmc.LOGERROR)
        return None

    except ValueError:
        if notify_errors:
            xbmcgui.Dialog().notification('AIOStreams', 'Invalid JSON response', xbmcgui.NOTIFICATION_ERROR)
        xbmc.log(f'[AIOStreams] Invalid JSON from: {url}', xbmc.LOGERROR)
        return None


@retry_on_sleep()
@retry_on_failure(max_retries=2, base_delay=1)
def resilient_get(url, headers=None, timeout=10):
    """
    Make a resilient GET request with retry logic.
    Automatically retries on connection errors and Android sleep issues.

    Args:
        url: URL to fetch
        headers: Optional request headers
        timeout: Request timeout

    Returns:
        Response object or raises exception
    """
    return requests.get(url, headers=headers, timeout=timeout)


@retry_on_sleep()
@retry_on_failure(max_retries=2, base_delay=1)
def resilient_post(url, headers=None, data=None, json_data=None, timeout=10):
    """
    Make a resilient POST request with retry logic.

    Args:
        url: URL to post to
        headers: Optional request headers
        data: Form data
        json_data: JSON data
        timeout: Request timeout

    Returns:
        Response object or raises exception
    """
    return requests.post(url, headers=headers, data=data, json=json_data, timeout=timeout)


class RequestSession:
    """
    Wrapper around requests.Session with retry logic and connection pooling.
    More efficient for multiple requests to the same host.
    """

    def __init__(self, max_retries=3, base_delay=1, timeout=10):
        """
        Initialize request session.

        Args:
            max_retries: Max retry attempts
            base_delay: Base delay for exponential backoff
            timeout: Default request timeout
        """
        self._session = requests.Session()
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._timeout = timeout

    def get(self, url, **kwargs):
        """Make GET request with retry logic."""
        return self._request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        """Make POST request with retry logic."""
        return self._request('POST', url, **kwargs)

    def _request(self, method, url, **kwargs):
        """Make request with retry logic."""
        kwargs.setdefault('timeout', self._timeout)

        last_exception = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_exception = e

                if attempt < self._max_retries:
                    delay = self._base_delay * (2 ** attempt)
                    xbmc.log(f'[AIOStreams] Request failed, retrying in {delay}s: {e}', xbmc.LOGWARNING)
                    time.sleep(delay)

        if last_exception:
            raise last_exception

    def close(self):
        """Close the session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
