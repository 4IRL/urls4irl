"""
Parses a URL, first using the url_normalize package, and then setting it to the https protocol.
Verifies that the URL is valid by using a HEAD method request. Checks if it redirects. If it does,
returns the URL the redirect pointed to. Otherwise, uses the original URL.

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            href                                             │
├──────────┬──┬─────────────────────┬─────────────────────┬───────────────────────────┬───────┤
│ protocol │  │        auth         │        host         │           path            │ hash  │
│          │  │                     ├──────────────┬──────┼──────────┬────────────────┤       │
│          │  │                     │   hostname   │ port │ pathname │     search     │       │
│          │  │                     │              │      │          ├─┬──────────────┤       │
│          │  │                     │              │      │          │ │    query     │       │
"  https:   //    user   :   pass   @ sub.host.com : 8080   /p/a/t/h  ?  query=string   #hash "
│          │  │          │          │   hostname   │ port │          │                │       │
│          │  │          │          ├──────────────┴──────┤          │                │       │
│ protocol │  │ username │ password │        host         │          │                │       │
├──────────┴──┼──────────┴──────────┼─────────────────────┤          │                │       │
│   origin    │                     │       origin        │ pathname │     search     │ hash  │
├─────────────┴─────────────────────┴─────────────────────┴──────────┴────────────────┴───────┤
│                                            href                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘    

"""

from url_normalize import url_normalize
import requests


class InvalidURLError(Exception):
    """Error if the URL returns a bad status code."""

    pass


def _parse_url(url: str) -> str:
    """
    Uses the url_normalize package to 'normalize' the URL as much as possible.
    It then sets all http protocols to https.
    There is a bug in the package that can return 'https:///' which is incorrect.
    This will search for that in the url string and make them or 'https://'.

    Args:
        url (str): The url sent for parsing

    Returns:
        str: The URL parsed per method above
    """
    return_val = url_normalize(url)
    https_prefix = "https://"
    http_prefix = "http://"

    if http_prefix in return_val:
        return_val = return_val.replace(http_prefix, https_prefix)

    if http_prefix + "/" in return_val:
        return_val = return_val.replace(http_prefix + "/", http_prefix)

    elif https_prefix + "/" in return_val:
        return_val = return_val.replace(https_prefix + "/", https_prefix)

    return return_val


def check_request_head(url: str) -> str:
    """
    Status codes: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status

    Sends the URL to get normalized to https method.
    Sends a head request to a parsed URL. If the request returns one of the status codes contained
    in BAD_STATUS_CODES below, returns 'Invalid'.

    If a redirect code is used, this will return the url included in the redirect http return header.

    Otherwise, returns the original URL if it receives a ~200 return code.

    Args:
        url (str): The URL to check for validity

    Raises:
        InvalidURLError: If the URL provided a bad status code on the HEAD request.

    Returns:
        str: Either the redirected URL, or the original URL used in the request head method
    """

    url = _parse_url(url)

    try:
        response = requests.head(url)

    except requests.exceptions.ConnectionError:
        raise InvalidURLError

    status_code = response.status_code

    BAD_STATUS_CODES = (400, 404, 406, 410, 414, 451, 505)

    if status_code in BAD_STATUS_CODES:
        raise InvalidURLError

    else:
        location = response.headers.get("Location", None)

        if location is None:
            # Can be a status code of 200 or other implying no redirect
            return url

        else:
            # Redirect was found, provide the redirect URL
            return location
