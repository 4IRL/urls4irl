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

from datetime import datetime
import random
import requests
from typing import Union
from url_normalize import url_normalize
from url_normalize.tools import deconstruct_url
from urllib.parse import unquote

if __name__ == "__main__":
    from strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS
else:
    from src.utils.strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS

USER_AGENTS = (
    "PostmanRuntime/7.40.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.1",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.79 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
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


def generate_headers(url: str, user_agent: str = None) -> dict[str, str]:
    return {
        VALIDATION_STRS.USER_AGENT: (
            generate_random_user_agent() if user_agent is None else user_agent
        ),
        VALIDATION_STRS.ACCEPT: "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        VALIDATION_STRS.ACCEPT_ENCODING: "*",
        VALIDATION_STRS.ACCEPT_LANGUAGE: "*",
        VALIDATION_STRS.SEC_FETCH_DEST: "document",
        VALIDATION_STRS.SEC_FETCH_MODE: "navigate",
        VALIDATION_STRS.SEC_FETCH_USER: "?1",
        VALIDATION_STRS.CONNECTION: "keep-alive",
        VALIDATION_STRS.HOST: deconstruct_url(url).host,
    }


def perform_head_request(url: str, user_agent: str = None) -> requests.Response:
    headers = generate_headers(url, user_agent)
    try:
        response = requests.head(
            url,
            timeout=(
                3,
                6,
            ),
            headers=headers,
        )
        if response.status_code in (
            403,
            405,
        ):
            # HEAD not allowed, try get
            return perform_get_request(url, headers)

    except requests.exceptions.ReadTimeout:
        # Try a get request instead
        return perform_get_request(url, headers)

    except requests.exceptions.SSLError as e:
        raise InvalidURLError("SSLError with the given URL. " + str(e))

    except requests.exceptions.ConnectionError as e:
        raise InvalidURLError("Unable to connect to the given URL. " + str(e))

    except requests.exceptions.MissingSchema as e:
        raise InvalidURLError("Invalid schema for this URL. " + str(e))

    else:
        return response


def perform_get_request(url: str, headers: dict[str, str]) -> requests.Response:
    try:
        response = requests.get(
            url,
            timeout=(
                3,
                6,
            ),
            headers=headers,
        )

        if response.status_code == 403:
            all_headers = (header.lower() for header in response.headers.keys())

            if (
                VALIDATION_STRS.CF_MITIGATED in all_headers
                or VALIDATION_STRS.CLOUDFLARE_SERVER
                == response.headers.get(VALIDATION_STRS.SERVER, None)
            ):
                """
                This generally indicates a Cloudflare challenge - bypass by checking archive records for the requested URL
                If a given response is valid, the "url" value of the response object is replaced with the requested URL from the user.
                This is because, if Wayback Archive is able to find the URL, we can consider it valid
                """
                internet_cache_response = perform_wayback_check(url, headers)
                if internet_cache_response is not None:
                    return internet_cache_response

            return response

    except requests.exceptions.ReadTimeout:
        return perform_both_all_user_agent_and_google_or_wayback_check(url, headers)

    except requests.exceptions.ConnectionError as e:
        raise InvalidURLError("Unable to connect to the given URL. " + str(e))

    except requests.exceptions.MissingSchema as e:
        raise InvalidURLError("Invalid schema for this URL. " + str(e))

    else:
        return response


def perform_both_all_user_agent_and_google_or_wayback_check(
    url: str, headers: dict[str, str]
) -> requests.Response:
    for idx in range(2):
        if idx == 0:
            try:
                return all_user_agent_sampling(url)
            except InvalidURLError:
                continue
        else:
            response = perform_wayback_check(url, headers)
            if response is not None:
                return response

    raise InvalidURLError("Unable to connect to and validate the URL.")


def perform_wayback_check(
    url: str, headers: dict[str, str]
) -> Union[None, requests.Response]:
    """
    Wayback archive responds with a found URL in the `links` property of the Response object.
    The Wayback archive is searched from 2020 onwards.
    The response contains an `original` property in the `links` property, which finally contains `url` property
        that contains the final URL.

    Both requests need to be narrowed down first to avoid redirects.

    Args:
        url (str): The normalized URL to look for
        headers (dict[str, str]): The headers being used, including the user's User-Agent

    Returns:
        Union[None, requests.Response]: A Response object if successful found in either internet cache, else None
    """
    # Iterate from year 2020 onwards for WayBack Archive
    current_year = datetime.now().year

    for year in range(2020, current_year + 1):
        wayback_archive_response = perform_head_request(
            VALIDATION_STRS.WAYBACK_ARCHIVE + str(year) + "/" + url,
            headers.get(VALIDATION_STRS.USER_AGENT),
        )
        if wayback_archive_response.status_code < 400:
            if wayback_archive_response.status_code >= 300:
                wayback_archive_response = perform_head_request(
                    wayback_archive_response.headers.get(VALIDATION_STRS.LOCATION),
                    headers.get(VALIDATION_STRS.USER_AGENT),
                )

            if wayback_archive_response.links:
                links_keys = (key.lower() for key in wayback_archive_response.links)
                if VALIDATION_STRS.ORIGINAL in links_keys:
                    url = wayback_archive_response.links[VALIDATION_STRS.ORIGINAL].get(
                        VALIDATION_STRS.URL, url
                    )

            wayback_archive_response.url = url
            wayback_archive_response.status_code = 200
            print(f"Waybacked: {url=}")
            return wayback_archive_response

    return None


def all_user_agent_sampling(url: str) -> requests.Response:
    for agent in USER_AGENTS:
        try:
            headers = generate_headers(url, user_agent=agent)
            response = requests.get(
                url,
                headers=headers,
                timeout=(
                    3,
                    6,
                ),
            )
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError as e:
            raise InvalidURLError("Unable to connect to the given URL. " + str(e))
        except requests.exceptions.MissingSchema as e:
            raise InvalidURLError("Invalid schema for this URL. " + str(e))
        else:
            return response

    raise InvalidURLError("Unable to connect to this URL.")


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
    response = perform_head_request(url, user_agent)

    status_code = response.status_code

    if status_code >= 400:
        raise InvalidURLError(
            "Unauthorized or could not find the given resource as the URL"
        )

    else:
        # Redirect or creation provides the Location header in http response
        if status_code in range(300, 400) or status_code == 201:
            location = response.headers.get(VALIDATION_STRS.LOCATION, None)
            location = response.next.url if location == "/" else location

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


if __name__ == "__main__":
    print(find_common_url("https://regex101.com/https://regex101.com/"))
    # print(find_common_url("www.stackoverflow.com"))
    # print(perform_wayback_check("www.stackoverflow.com", headers=generate_headers("www.stackoverflow.com")))
