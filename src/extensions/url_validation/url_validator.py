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

from flask import Flask


if __name__ == "__main__":
    # TODO: Change imports when running as standalone module
    from utils.strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS
    from constants import COMMON_REDIRECTS, USER_AGENTS
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
        self, url: str, user_agent: str | None = None
    ) -> requests.Response:
        headers = self._generate_headers(url, user_agent)
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
                return self._perform_get_request(url, headers)

        except requests.exceptions.ReadTimeout:
            # Try a get request instead
            return self._perform_get_request(url, headers)

        except requests.exceptions.SSLError as e:
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
                    internet_cache_response = self._perform_wayback_check(url, headers)
                    if internet_cache_response is not None:
                        return internet_cache_response

                return response

        except requests.exceptions.ReadTimeout:
            return self._perform_both_all_user_agent_and_wayback_check(url, headers)

        except requests.exceptions.ConnectionError as e:
            raise InvalidURLError("Unable to connect to the given URL. " + str(e))

        except requests.exceptions.MissingSchema as e:
            raise InvalidURLError("Invalid schema for this URL. " + str(e))

        else:
            return response

    def _perform_both_all_user_agent_and_wayback_check(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        for idx in range(2):
            if idx == 0:
                try:
                    return self._all_user_agent_sampling(url)
                except InvalidURLError:
                    continue
            else:
                response = self._perform_wayback_check(url, headers)
                if response is not None:
                    return response

        raise InvalidURLError("Unable to connect to and validate the URL.")

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
                headers.get(VALIDATION_STRS.USER_AGENT),
            )
            if wayback_archive_response.status_code < 400:
                if wayback_archive_response.status_code >= 300:
                    wayback_archive_response = self._perform_head_request(
                        wayback_archive_response.headers.get(
                            VALIDATION_STRS.LOCATION, ""
                        ),
                        headers.get(VALIDATION_STRS.USER_AGENT),
                    )

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

    def find_full_path_normalized_url(
        self, url: str, user_agent: str | None = None
    ) -> str:
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
            return self._normalize_url(url)
        url = self._normalize_url(url)
        response = self._perform_head_request(url, user_agent)

        status_code = response.status_code

        if status_code >= 400:
            raise InvalidURLError(
                "Unauthorized or could not find the given resource as the URL"
            )

        else:
            # Redirect or creation provides the Location header in http response
            if status_code in range(300, 400) or status_code == 201:
                location = response.headers.get(VALIDATION_STRS.LOCATION, None)
                if response.next is not None:
                    location = response.next.url if location == "/" else location

            else:
                location = response.url

            if location is None:
                # Can be a status code of 200 or other implying no redirect, or does not include Location header
                return url

            else:
                if status_code == 302 and any(
                    (
                        common_redirect in location
                        for common_redirect in COMMON_REDIRECTS
                    )
                ):
                    # Common redirects, where sometimes 'www.facebook.com' could send you to the following:
                    #       'https://www.facebook.com/login/?next=https%3A%2F%2Fwww.facebook.com%2F'
                    # Forces the return of 'https://www.facebook.com', which comes after the ?next= query param
                    return self._filter_out_common_redirect(url)

                # Redirect was found, provide the redirect URL
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
    print("Trying to run as script")
