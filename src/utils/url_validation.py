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
from urllib.parse import unquote
import random
import requests

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
)

COMMON_REDIRECTS = {
    "https://www.facebook.com/login/?next=",
}


class InvalidURLError(Exception):
    """Error if the URL returns a bad status code."""

    pass


def normalize_url(url: str) -> str:
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


def generate_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def perform_head_request(url: str) -> requests.Response:
    random_user_agent = generate_random_user_agent()
    try:
        headers = {
            "User-Agent": random_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }
        response = requests.head(url, timeout=5, headers=headers)

    except requests.exceptions.ReadTimeout:
        # Try a get request instead
        return perform_get_request(url, random_user_agent)

    except requests.exceptions.ConnectionError:
        raise InvalidURLError

    except requests.exceptions.MissingSchema:
        raise InvalidURLError

    else:
        return response


def perform_get_request(url: str, random_user_agent: str) -> requests.Response:
    try:
        headers = {
            "User-Agent": random_user_agent,
        }
        response = requests.get(url, timeout=10, headers=headers)

    except requests.exceptions.ReadTimeout:
        raise InvalidURLError

    except requests.exceptions.ConnectionError:
        raise InvalidURLError

    except requests.exceptions.MissingSchema:
        raise InvalidURLError

    else:
        return response


def find_common_url(url: str, user_agent: str = None) -> str:
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

    url = normalize_url(url)
    response = perform_head_request(url)

    status_code = response.status_code

    if status_code >= 400:
        raise InvalidURLError

    else:
        # Redirect or creation provides the Location header in http response
        if status_code in range(300, 400) or status_code == 201:
            location = response.headers.get("Location", None)

        else:
            location = response.url

        if location is None:
            # Can be a status code of 200 or other implying no redirect, or does not include Location header
            return url

        else:
            if status_code == 302 and any(
                (common_redirect in location for common_redirect in COMMON_REDIRECTS)
            ):
                # Common redirects, where sometimes 'www.facebook.com' could send you to the following:
                #       'https://www.facebook.com/login/?next=https%3A%2F%2Fwww.facebook.com%2F'
                # Forces the return of 'https://www.facebook.com', which comes after the ?next= query param
                return filter_out_common_redirect(url)

            # Redirect was found, provide the redirect URL
            return location


def filter_out_common_redirect(url: str) -> str:
    for common_redirect in COMMON_REDIRECTS:
        if common_redirect in url:
            url = url.removeprefix(common_redirect)
            return unquote(url)

    return unquote(url)
