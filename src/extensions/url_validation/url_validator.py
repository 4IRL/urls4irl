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
import socket
from typing import Tuple, Union
from url_normalize import url_normalize
from url_normalize.tools import deconstruct_url
from urllib.parse import unquote

from flask import Flask


if __name__ == "__main__":
    # TODO: Change imports when running as standalone module
    from utils.strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS
    from extensions.url_validation.constants import COMMON_REDIRECTS, USER_AGENTS
else:
    from src.utils.strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS
    from src.extensions.url_validation.constants import COMMON_REDIRECTS, USER_AGENTS


class InvalidURLError(Exception):
    """Error if the URL returns a bad status code."""

    pass


class UrlValidator:
    def __init__(self) -> None:
        self._ui_testing = False

    def init_app(self, app: Flask) -> None:
        app.extensions[VALIDATION_STRS.URL_VALIDATION_MODULE] = self
        is_testing: bool = app.config.get("TESTING", False)
        is_production: bool = app.config.get("PRODUCTION", False)
        is_ui_testing: bool = app.config.get("UI_TESTING", False)
        is_not_production_and_is_testing_ui = (
            not is_production and is_testing and is_ui_testing
        )
        self._ui_testing: bool = is_not_production_and_is_testing_ui

    def _normalize_url(self, url: str) -> str:
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
        return_val = str(url_normalize(url))
        https_prefix = "https://"
        http_prefix = "http://"

        if http_prefix in return_val:
            return_val = return_val.replace(http_prefix, https_prefix)

        if http_prefix + "/" in return_val:
            return_val = return_val.replace(http_prefix + "/", http_prefix)

        elif https_prefix + "/" in return_val:
            return_val = return_val.replace(https_prefix + "/", https_prefix)

        return return_val

    def _generate_headers(
        self, url: str, user_agent: str | None = None
    ) -> dict[str, str]:
        return {
            VALIDATION_STRS.USER_AGENT: (
                self.generate_random_user_agent() if user_agent is None else user_agent
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

    def _perform_head_request(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response | None:
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
                return None

        except requests.exceptions.ReadTimeout:
            # Try a get request instead
            return None

        except requests.exceptions.SSLError as e:
            if "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(e):
                # Check wayback for these, else let it fail in the GET request
                return self._perform_wayback_check(url, headers)
            raise InvalidURLError("SSLError with the given URL. " + str(e))

        except requests.exceptions.ConnectionError as e:
            raise InvalidURLError("Unable to connect to the given URL. " + str(e))

        except requests.exceptions.MissingSchema as e:
            raise InvalidURLError("Invalid schema for this URL. " + str(e))

        else:
            return response

    def _perform_get_request(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        try:
            response = requests.get(
                url,
                timeout=(
                    3,
                    6,
                ),
                headers=headers,
            )

        except requests.exceptions.ReadTimeout:
            return self._all_user_agent_sampling(url)

        except requests.exceptions.ConnectionError as e:
            raise InvalidURLError("Unable to connect to the given URL. " + str(e))

        except requests.exceptions.MissingSchema as e:
            raise InvalidURLError("Invalid schema for this URL. " + str(e))

        else:
            return response

    def _all_user_agent_sampling(self, url: str) -> requests.Response:
        for agent in USER_AGENTS:
            try:
                headers = self._generate_headers(url, user_agent=agent)
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

    def _perform_wayback_check(
        self, url: str, headers: dict[str, str]
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
            wayback_archive_response = self._perform_head_request(
                VALIDATION_STRS.WAYBACK_ARCHIVE + str(year) + "/" + url,
                headers,
            )
            if wayback_archive_response is None:
                continue

            if wayback_archive_response.status_code < 400:
                if wayback_archive_response.status_code >= 300:
                    wayback_archive_response = self._perform_head_request(
                        wayback_archive_response.headers.get(
                            VALIDATION_STRS.LOCATION, ""
                        ),
                        headers,
                    )
                    if wayback_archive_response is None:
                        continue

                if wayback_archive_response.links:
                    links_keys = (key.lower() for key in wayback_archive_response.links)
                    if VALIDATION_STRS.ORIGINAL in links_keys:
                        url = wayback_archive_response.links[
                            VALIDATION_STRS.ORIGINAL
                        ].get(VALIDATION_STRS.URL, url)

                wayback_archive_response.url = url
                wayback_archive_response.status_code = 200
                print(f"Waybacked: {url=}")
                return wayback_archive_response

        return None

    def _validate_host(self, host: str) -> bool:
        try:
            host_by_name = socket.gethostbyname(host)
            return host_by_name != ""

        except socket.gaierror as e:
            raise InvalidURLError("This domain is invalid. " + str(e))

        except socket.timeout as e:
            raise InvalidURLError("DNS lookup timed out. " + str(e))

        except socket.herror as e:
            raise InvalidURLError(
                "Host-related error, unable to validate this domain. " + str(e)
            )

        except socket.error as e:
            raise InvalidURLError(
                "Unknown error leading to issues validating domain. " + str(e)
            )

        except Exception as e:
            raise InvalidURLError("Unexpected error occurred. " + str(e))

    def validate_url(self, url: str, user_agent: str | None = None) -> Tuple[str, bool]:
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
        if self._ui_testing:
            return self._normalize_url(url), True

        # First normalize the URL
        url = self._normalize_url(url)
        deconstructed = deconstruct_url(url)

        # Check for proper schema
        if deconstructed.scheme != "https":
            raise InvalidURLError("Improper scheme given for this URL")

        # DNS Check to ensure valid domain and host
        if not self._validate_host(deconstructed.host):
            raise InvalidURLError("Domain did not resolve into a valid IP address.")

        # Build headers to perform HTTP request to validate URL
        headers = self._generate_headers(url, user_agent)

        # Perform HEAD request, majority of URLs should be okay with this
        response = self._perform_head_request(url, headers)

        if response is None:
            response = self._perform_get_request(url, headers)

        if response.status_code == 404:
            raise InvalidURLError("Could not find the given resource at the URL")

        # Validates the response from a HEAD or GET request
        location = self._check_for_valid_response_location(url, response)
        if location is not None:
            return location, True

        if response.status_code >= 400 and response.status_code < 500:
            response = self._perform_wayback_check(url, headers)

        if response is None:
            raise InvalidURLError("Unable to validate this URL")

        # Validates the Wayback response
        location = self._check_for_valid_response_location(url, response)
        if location is not None:
            return location, True

        """
        At this point, the URL has a proper schema, and has had the domain + host validated.
        The URL has failed a HEAD and GET from this server.
        The URL has failed a wayback request.
        The URL may have a fully JavaScript based frontend, which would make these traditional methods more difficult.
        We provide back the normalized URL and mark the URL as UNKNOWN, to be later verified by a headless automated browser.
        """
        return url, False

    def _check_for_valid_response_location(
        self, url: str, response: requests.Response
    ) -> str | None:
        location = None
        status_code = response.status_code

        # Check for success
        if status_code == 200:
            location = response.url
            if location is None:
                location = url

            return location

        # Check for redirects
        if status_code in range(300, 400) or status_code == 201:
            location = response.headers.get(VALIDATION_STRS.LOCATION, None)
            if response.next is not None:
                location = response.next.url if location == "/" else location

        # Check for more common redirectes
        if (
            location is not None
            and status_code == 302
            and any(
                (common_redirect in location for common_redirect in COMMON_REDIRECTS)
            )
        ):
            # Common redirects, where sometimes 'www.facebook.com' could send you to the following:
            #       'https://www.facebook.com/login/?next=https%3A%2F%2Fwww.facebook.com%2F'
            # Forces the return of 'https://www.facebook.com', which comes after the ?next= query param
            return self._filter_out_common_redirect(url)

        return location

    @staticmethod
    def _filter_out_common_redirect(url: str) -> str:
        for common_redirect in COMMON_REDIRECTS:
            if common_redirect in url:
                url = url.removeprefix(common_redirect)
                return unquote(url)

        return unquote(url)

    @staticmethod
    def generate_random_user_agent() -> str:
        return random.choice(USER_AGENTS)


if __name__ == "__main__":
    validator = UrlValidator()
    INVALID_URLS = (
        "https://www.lowes.com/pd/ReliaBilt-ReliaBilt-3-1-2-in-Zinc-Plated-Flat-Corner-Brace-4-Pack/5003415919",
        "https://www.upgrad.com/blog/top-artificial-intelligence-project-ideas-topics-for-beginners/",
        # "https://www.fnb-online.com/",
        "fnb-online.com/",
        "https://www.fnb-online.com/personal",
        "https://a.co/d/7jJVnzT",
    )

    print(validator.validate_url(INVALID_URLS[2]))
    # for invalid_url in INVALID_URLS:
    #    print(validator.validate_url(invalid_url))
    print("Trying to run as script")
