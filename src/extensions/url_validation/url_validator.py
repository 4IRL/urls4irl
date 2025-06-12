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
import os
import random
import time
import requests
import socket
from typing import Tuple, Union
from urllib.parse import unquote, urljoin

import redis
from redis.client import Redis
from requests.structures import CaseInsensitiveDict
from url_normalize import url_normalize
from url_normalize.tools import deconstruct_url

from flask import Flask

from src.app_logger import (
    critical_log,
    error_log,
    info_log,
    safe_add_log,
    safe_add_many_logs,
    warning_log,
)


if __name__ == "__main__":
    # TODO: Change imports when running as standalone module
    from utils.strings.config_strs import CONFIG_ENVS as ENV
    from utils.strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS
    from extensions.url_validation.constants import (
        COMMON_REDIRECTS,
        USER_AGENTS,
    )
else:
    from src.utils.strings.config_strs import CONFIG_ENVS as ENV
    from src.utils.strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS
    from src.extensions.url_validation.constants import (
        COMMON_REDIRECTS,
        USER_AGENTS,
    )


class InvalidURLError(Exception):
    """Error if the URL returns a bad status code."""

    pass


class WaybackRateLimited(Exception):
    """Error if too many attempts for Wayback within 1 minute."""

    pass


class UrlValidator:
    def __init__(self, is_testing: bool = False) -> None:
        self._ui_testing = False
        self._is_testing = is_testing
        self._redis_uri = os.environ.get(ENV.REDIS_URI, None)
        self.timer = None
        self._has_app = False

    def init_app(self, app: Flask) -> None:
        app.extensions[VALIDATION_STRS.URL_VALIDATION_MODULE] = self
        is_testing: bool = app.config.get("TESTING", False)
        is_production: bool = app.config.get("PRODUCTION", False)
        is_ui_testing: bool = app.config.get("UI_TESTING", False)
        is_debug: bool = app.config.get("FLASK_DEBUG", False)
        is_not_production_and_is_testing_ui = (
            not is_production and is_testing and is_ui_testing
        )
        self._ui_testing: bool = is_not_production_and_is_testing_ui
        self._redis_uri = app.config.get(ENV.REDIS_URI, None)
        self._is_testing = is_testing
        self._has_app = is_testing or is_production or is_ui_testing or is_debug

    def _log(self, log_fn, log):
        log_fn(log) if self._has_app else None

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
        self, url: str, user_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        headers = (
            {}
            if user_headers is None
            else {key: val for key, val in user_headers.items()}
        )
        if VALIDATION_STRS.USER_AGENT not in headers:
            headers[VALIDATION_STRS.USER_AGENT] = self.generate_random_user_agent()

        if VALIDATION_STRS.ACCEPT not in headers:
            headers[VALIDATION_STRS.ACCEPT] = (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            )

        if VALIDATION_STRS.ACCEPT_ENCODING not in headers:
            headers[VALIDATION_STRS.ACCEPT_ENCODING] = "*"

        if VALIDATION_STRS.ACCEPT_LANGUAGE not in headers:
            headers[VALIDATION_STRS.ACCEPT_LANGUAGE] = (
                "en-US, en;q=0.9" if self._is_testing else "*"
            )

        if VALIDATION_STRS.SEC_FETCH_DEST not in headers:
            headers[VALIDATION_STRS.SEC_FETCH_DEST] = "document"

        if (
            VALIDATION_STRS.SEC_FETCH_MODE not in headers
            or headers.get(VALIDATION_STRS.SEC_FETCH_MODE, "").lower() == "cors"
        ):
            headers[VALIDATION_STRS.SEC_FETCH_MODE] = "navigate"

        if VALIDATION_STRS.SEC_FETCH_USER not in headers:
            headers[VALIDATION_STRS.SEC_FETCH_USER] = "?1"

        if VALIDATION_STRS.CONNECTION not in headers:
            headers[VALIDATION_STRS.CONNECTION] = "keep-alive"

        # Remove invalid headers before making URL validation request
        header_keys = list(headers)
        for header in header_keys:
            if header.lower() in VALIDATION_STRS.INVALID_HEADERS:
                headers.pop(header)

        headers[VALIDATION_STRS.HOST] = deconstruct_url(url).host
        return headers

    def _perform_head_request(
        self, url: str, headers: dict[str, str], limited_redirects: bool = False
    ) -> requests.Response | None:
        try:
            if limited_redirects:
                self._log(
                    safe_add_log, "Performing HEAD request with limited redirects"
                )
                response = self._perform_head_with_custom_redirect(url, headers)
            else:
                self._log(safe_add_log, "Performing HEAD request with no redirects")
                response = self._perform_head_with_no_redirects(url, headers)

        except requests.exceptions.ReadTimeout:
            self._log(safe_add_log, "Read timed out with HEAD request")
            return None

        except requests.exceptions.TooManyRedirects:
            self._log(
                warning_log, "Too many redirects exception with custom HEAD redirect"
            )
            return self._perform_head_request(url, headers, limited_redirects=False)

        except requests.exceptions.SSLError as e:
            if "UNSAFE_LEGACY_RENEGOTIATION_DISABLED" in str(e):
                # Check wayback for these, else let it fail in the GET request
                self._log(
                    safe_add_log,
                    "UNSAFE_LEGACY_RENEGOTIATION_DISABLED in HEAD response",
                )
                return self._perform_wayback_check(url, headers)
            self._log(warning_log, "SSLError with given URL")
            raise InvalidURLError("SSLError with the given URL. " + str(e))

        except requests.exceptions.ConnectionError as e:
            self._log(
                warning_log, "Unable to connect to the given URL with HEAD request"
            )
            raise InvalidURLError("Unable to connect to the given URL. " + str(e))

        except requests.exceptions.MissingSchema as e:
            self._log(warning_log, f"Missing schema in HEAD request for: {url}")
            raise InvalidURLError("Missing schema for this URL. " + str(e))

        except requests.exceptions.InvalidSchema as e:
            self._log(warning_log, f"Invalid schema in HEAD request for: {url}")
            raise InvalidURLError(f"Invalid schema for this URL. | {url=} |" + str(e))

        else:
            return response

    def _perform_head_with_custom_redirect(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response | None:
        max_num_redirects = 10
        num_redirects = 0
        redirect_url = None
        self._log(info_log, f"Trying HEAD redirect with {url=}")

        response: requests.Response = requests.head(
            url,
            timeout=(
                3,
                4,
            ),
            headers=headers,
            allow_redirects=False,
        )

        while response.is_redirect or response.is_permanent_redirect:
            if num_redirects >= max_num_redirects or response.status_code in range(
                400, 600
            ):
                self._log(safe_add_log, f"HEAD Too many redirects: {num_redirects}")
                return None
            elif response.status_code in range(400, 600):
                self._log(
                    safe_add_log, f"HEAD Response status code: {response.status_code}"
                )
                return None
            original_url: str = redirect_url if redirect_url is not None else url

            redirect_url = response.headers.get(VALIDATION_STRS.LOCATION, "")
            if (
                response.next
                and response.next.url
                and deconstruct_url(response.next.url).scheme == "https"
            ):
                self._log(
                    safe_add_log, f"HEAD Redirect found next URL: {response.next.url}"
                )
                redirect_url = response.next.url

            elif not deconstruct_url(redirect_url).scheme == "https":
                redirect_url = urljoin(original_url, redirect_url)
                self._log(safe_add_log, f"HEAD constructed next url: {redirect_url}")

            self._log(info_log, f"Trying HEAD redirect with {redirect_url=}")
            if self.has_android_user_agent_and_intent_url(
                user_agent=headers[VALIDATION_STRS.USER_AGENT], url=redirect_url
            ):
                # If an intent was returned, then the original URL was valid
                # Override HTTP status code and return the response to indicate valid URL
                self._log(info_log, "User has Android and URL was an intent")
                response.status_code = 200
                return response
            response = requests.head(
                redirect_url,
                timeout=(
                    3,
                    4,
                ),
                headers=headers,
                allow_redirects=False,
            )
            num_redirects += 1

        self._log(
            safe_add_many_logs,
            [
                f"From HEAD request with redirect: {response.headers} ",
                f"{redirect_url=}",
                f"{response.url=}",
            ],
        )
        return response

    def _perform_head_with_no_redirects(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response | None:
        self._log(info_log, f"Trying HEAD with no redirect on {url=}")
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
            self._log(
                safe_add_log,
                f"HEAD request failed with status code {response.status_code}",
            )
            return None

        self._log(
            safe_add_many_logs,
            (
                [
                    f"From HEAD request without redirect: {response.headers} ",
                    f"{url=}",
                    f"{response.url=}",
                ]
            ),
        )
        return response

    def _perform_get_request(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        try:
            response = self._perform_get_with_custom_redirect(url, headers)

        except requests.exceptions.ReadTimeout:
            self._log(warning_log, "Read timed out with GET request")
            return self._all_user_agent_sampling(url, headers)

        except requests.exceptions.ConnectionError as e:
            self._log(
                warning_log, "Unable to connect to the given URL with GET request"
            )
            raise InvalidURLError("Unable to connect to the given URL. " + str(e))

        except requests.exceptions.MissingSchema as e:
            self._log(warning_log, f"Missing schema in GET request for: {url}")
            raise InvalidURLError("Missing schema for this URL. " + str(e))

        except requests.exceptions.TooManyRedirects as e:
            self._log(
                warning_log, "Too many redirects exception with custom GET redirect"
            )
            raise InvalidURLError("Too many redirects for this URL. " + str(e))

        except requests.exceptions.InvalidSchema as e:
            self._log(warning_log, f"Invalid schema in GET request for: {url}")
            raise InvalidURLError("Invalid schema for this URL. " + str(e))

        else:
            return response

    def _perform_get_with_custom_redirect(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        max_num_redirects = 10
        num_redirects = 0
        redirect_url = None

        self._log(info_log, f"Trying GET redirect with {url=}")
        response: requests.Response = requests.get(
            url,
            timeout=(
                3,
                4,
            ),
            headers=headers,
            allow_redirects=False,
        )

        while response.is_redirect or response.is_permanent_redirect:
            if num_redirects >= max_num_redirects:
                self._log(safe_add_log, f"Too many redirects: {num_redirects}")
                return response
            elif response.status_code in range(400, 600):
                self._log(safe_add_log, f"Response status code: {response.status_code}")
                return response

            redirect_url = response.headers.get(VALIDATION_STRS.LOCATION, "")

            # Check for proper schema, some responses include a relative URL in the LOCATION header
            # so that needs to be checked here as well
            original_url: str = redirect_url if redirect_url is not None else url

            redirect_url = response.headers.get(VALIDATION_STRS.LOCATION, "")
            if (
                response.next
                and response.next.url
                and deconstruct_url(response.next.url).scheme == "https"
            ):
                self._log(
                    safe_add_log, f"GET Redirect found next URL: {response.next.url}"
                )
                redirect_url = response.next.url

            elif not deconstruct_url(redirect_url).scheme == "https":
                redirect_url = urljoin(original_url, redirect_url)
                self._log(safe_add_log, f"GET constructed next url: {redirect_url}")

            self._log(info_log, f"Trying GET redirect with {redirect_url=}")
            if self.has_android_user_agent_and_intent_url(
                user_agent=headers[VALIDATION_STRS.USER_AGENT], url=redirect_url
            ):
                # If an intent was returned, then the original URL was valid
                # Override HTTP status code and return the response to indicate valid URL
                self._log(info_log, "User has Android and URL was an intent")
                response.status_code = 200
                return response
            response = requests.get(
                redirect_url,
                timeout=(
                    3,
                    4,
                ),
                headers=headers,
                allow_redirects=False,
            )
            num_redirects += 1

        self._log(
            safe_add_many_logs,
            [
                f"From GET request with redirect: {response.headers} ",
                f"{redirect_url=}",
                f"{response.url=}",
            ],
        )
        return response

    def _all_user_agent_sampling(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        self._log(info_log, f"Trying all user agent sampling for: {url}")
        for agent in USER_AGENTS:
            try:
                self._log(info_log, f"Trying: {agent}")
                headers[VALIDATION_STRS.USER_AGENT] = agent
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=(
                        3,
                        6,
                    ),
                )
            except requests.exceptions.ReadTimeout:
                if self.timer and (time.perf_counter() - self.timer) >= 30:
                    self._log(
                        warning_log,
                        "Could not validate URL with sampled agents within 30 seconds",
                    )
                    raise InvalidURLError("Unable to validate URL within 30 seconds.")
                continue
            except requests.exceptions.ConnectionError as e:
                self._log(warning_log, "Could not connect to URL with sampled agents")
                raise InvalidURLError("Unable to connect to the given URL. " + str(e))
            except requests.exceptions.MissingSchema as e:
                self._log(warning_log, "Invalid schema for URL with sampled agents")
                raise InvalidURLError("Invalid schema for this URL. " + str(e))
            except requests.exceptions.TooManyRedirects as e:
                self._log(warning_log, "Too many redirects for URL with sampled agents")
                raise InvalidURLError("Too many redirects for this URL. " + str(e))
            else:
                return response

        self._log(critical_log, "Unable to connect to url after sampling agents")
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
        try:
            # Iterate from year 2020 onwards for WayBack Archive
            current_year = datetime.now().year

            redis_client: Redis | None = None
            if self._redis_uri and self._redis_uri != "memory://":
                redis_client = redis.Redis.from_url(self._redis_uri)  # type: ignore

            for year in range(2020, current_year + 1):
                is_rate_limited = redis_client and self._is_wayback_rate_limited(
                    redis_client
                )
                if is_rate_limited:
                    self._log(critical_log, "Rate limited using Wayback")
                    raise WaybackRateLimited(
                        "Too many Wayback attempts, please wait a minute."
                    )

                wayback_url = VALIDATION_STRS.WAYBACK_ARCHIVE + str(year) + "/" + url
                self._log(info_log, f"Checking year {year} in Wayback | {wayback_url}")
                wayback_archive_response = self._perform_head_request(
                    wayback_url,
                    headers,
                )
                if wayback_archive_response is None:
                    self._log(safe_add_log, f"No response provided for year {year}")
                    continue

                wayback_status_code = wayback_archive_response.status_code
                if wayback_status_code not in range(200, 400):
                    self._log(
                        safe_add_log,
                        f"Wayback response status code: {wayback_status_code}",
                    )
                    continue

                if 300 <= wayback_status_code < 400:
                    is_rate_limited = redis_client and self._is_wayback_rate_limited(
                        redis_client
                    )
                    if is_rate_limited:
                        self._log(
                            critical_log, "Rate limited using Wayback in redirect"
                        )
                        raise WaybackRateLimited(
                            "Too many Wayback attempts, please wait a minute."
                        )

                    redirect_url = wayback_archive_response.headers.get(
                        VALIDATION_STRS.LOCATION, ""
                    )
                    self._log(
                        safe_add_log,
                        f"Found redirect using Wayback log, status code: {wayback_status_code} | url: {redirect_url}",
                    )
                    wayback_archive_response = self._perform_head_request(
                        redirect_url,
                        headers,
                    )
                    if wayback_archive_response is None:
                        self._log(
                            safe_add_log, "No response from wayback redirect response"
                        )
                        continue

                if wayback_archive_response.links:
                    links_keys = (key.lower() for key in wayback_archive_response.links)
                    if VALIDATION_STRS.ORIGINAL in links_keys:
                        url = wayback_archive_response.links[
                            VALIDATION_STRS.ORIGINAL
                        ].get(VALIDATION_STRS.URL, url)

                wayback_archive_response.url = url
                wayback_archive_response.status_code = 200
                self._log(
                    safe_add_many_logs,
                    [
                        "Successfully found URL with Wayback",
                        f"Waybacked URL: {url}",
                    ],
                )

                print(f"Waybacked: {url=}")

                return wayback_archive_response

            self._log(warning_log, "Could not validate URL using Wayback")
            return None

        except requests.exceptions.ConnectionError:
            self._log(warning_log, "Connection error using Wayback")
            raise WaybackRateLimited("Wayback experienced a ConnectionError")

    def _get_current_minute_window(self) -> int:
        return int(datetime.now().timestamp())

    def _is_wayback_rate_limited(self, redis_client: Redis) -> bool:
        time_window = 60  # Time window for rate limit is 60 seconds
        max_requests = 10
        current_minute_window = self._get_current_minute_window() // time_window
        redis_key = f"wayback_ratelimit:{current_minute_window}"

        request_count = redis_client.get(redis_key)
        if request_count is None:
            redis_client.set(redis_key, 1, ex=time_window)
            return False

        request_count = int(request_count)  # type: ignore

        if request_count >= max_requests:
            return True

        redis_client.incr(redis_key)
        return False

    def _validate_host(self, host: str) -> bool:
        try:
            host_by_name = socket.gethostbyname(host)
            return host_by_name != ""

        except socket.gaierror as e:
            self._log(warning_log, f"Host domain is invalid: {host}")
            raise InvalidURLError("This domain is invalid. " + str(e))

        except socket.timeout as e:
            self._log(warning_log, f"DNS timed out for domain: {host}")
            raise InvalidURLError("DNS lookup timed out. " + str(e))

        except socket.herror as e:
            self._log(warning_log, f"Host related error: {host}")
            raise InvalidURLError(
                "Host-related error, unable to validate this domain. " + str(e)
            )

        except socket.error as e:
            self._log(critical_log, f"Unknown error validating host error: {host}")
            raise InvalidURLError(
                "Unknown error leading to issues validating domain. " + str(e)
            )

        except Exception as e:
            self._log(error_log, f"Unexpected error validating host error: {host}")
            raise InvalidURLError("Unexpected error occurred. " + str(e))

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

            if any(common_redirect in location for common_redirect in COMMON_REDIRECTS):
                self._log(safe_add_log, "Filtering out common redirect on 200")
                location = self._filter_out_common_redirect(url)

            deconstructed = deconstruct_url(location)

            # Check for proper schema
            if deconstructed.scheme == "https":
                self._log(
                    safe_add_log, f"Valid schema on deconstructed URL: {location}"
                )
                return location

        # Check for redirects
        if status_code in range(300, 400) or status_code == 201:
            location = response.headers.get(VALIDATION_STRS.LOCATION, None)
            if response.next is not None:
                location = response.next.url if location == "/" else location

            deconstructed = deconstruct_url(location)

            # Check for proper schema
            if deconstructed.scheme != "https":
                location = None

        # Check for more common redirects
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
            self._log(
                safe_add_log, "Filtering out common redirect on redirect with 302"
            )
            return self._filter_out_common_redirect(url)

        # Check for proper schema
        if location is not None and deconstruct_url(location).scheme != "https":
            self._log(warning_log, f"Invalid schema on deconstructed URL: {location}")
            return None

        return (
            self._filter_out_common_redirect(location)
            if location is not None
            else location
        )

    def _check_if_is_short_url(self, url_domain: str) -> bool:
        if not self._redis_uri or self._redis_uri == "memory://":
            self._log(warning_log, "Redis unavailable to check for short URL")
            return False

        redis_client: Redis = redis.Redis.from_url(self._redis_uri)  # type: ignore
        return redis_client.sismember(VALIDATION_STRS.SHORT_URLS, url_domain) == 1

    def _validate_short_url(
        self, url: str, headers: dict[str, str]
    ) -> Tuple[str, bool]:
        MAX_RETRY_ATTEMPTS = 5
        try:
            for idx in range(MAX_RETRY_ATTEMPTS):
                self._log(
                    info_log, f"Attempt: {idx + 1} | Trying to validate shortened URL"
                )
                response = requests.get(
                    url, headers=headers, allow_redirects=False, timeout=10
                )

                if response.status_code == 404:
                    raise InvalidURLError("Invalid shortened URL.")

                if response.status_code == 200:
                    # Sometimes initial attempts at lengthening a URL produces the same URL
                    # Retry again to see if next attempt will put out long URL
                    deconstructed_url = deconstruct_url(response.url)
                    if self._check_if_is_short_url(deconstructed_url.host):
                        continue
                    return response.url, True

                if response.status_code in range(300, 400):
                    if response.next is not None and response.next.url:
                        self._log(
                            safe_add_many_logs,
                            [
                                "Validated short URL",
                                f"Short URL: {url}",
                                f"Long URL: {response.next.url}",
                            ],
                        )
                        return response.next.url, True

                    if VALIDATION_STRS.LOCATION in response.headers:
                        self._log(
                            safe_add_many_logs,
                            [
                                "Validated short URL",
                                f"Short URL: {url}",
                                f"Long URL: {response.headers[VALIDATION_STRS.LOCATION]}",
                            ],
                        )
                        return response.headers[VALIDATION_STRS.LOCATION], True

        except requests.exceptions.ReadTimeout as e:
            self._log(warning_log, "Short URL request timed out on GET")
            raise InvalidURLError("Timed out trying to read this short URL. " + str(e))
        except requests.exceptions.ConnectionError as e:
            self._log(warning_log, "Unable to connect to short URL request on GET")
            raise InvalidURLError("Unable to connect to the short URL. " + str(e))
        except requests.exceptions.MissingSchema as e:
            self._log(warning_log, "Invalid schema for short URL request on GET")
            raise InvalidURLError("Invalid schema for this short URL. " + str(e))
        except requests.RequestException as e:
            self._log(warning_log, "Unable to validate short URL request on GET")
            raise InvalidURLError("Unable to validate short URL. " + str(e))

        else:
            return url, False

    def validate_url(
        self, url: str | None, user_headers: dict[str, str] | None = None
    ) -> Tuple[str, bool]:
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
        self.timer = time.perf_counter()
        if not url:
            raise InvalidURLError("URL cannot be empty")

        # First normalize the URL
        url = self._normalize_url(url)
        self._log(safe_add_log, f"Normalized URL for validation: {url}")
        deconstructed = deconstruct_url(url)

        # Check for proper schema
        if deconstructed.scheme != "https":
            self._log(warning_log, "URL schema was not https")
            raise InvalidURLError("Improper scheme given for this URL")

        # Return during UI testing here so we can check ill-formed URLs and behavior on frontend
        if self._ui_testing:
            self._log(safe_add_log, "Returning given URL while in testing...")
            return self._return_url_for_ui_testing(user_headers, url)

        # DNS Check to ensure valid domain and host
        self._log(safe_add_log, f"Validating host: {deconstructed.host}")
        if not self._validate_host(deconstructed.host):
            raise InvalidURLError("Domain did not resolve into a valid IP address")

        # Build headers to perform HTTP request to validate URL
        headers = self._generate_headers(url, user_headers)
        self._log(safe_add_log, f"Using headers:\n{headers}")

        # Check if contained within short URL domains
        if self._check_if_is_short_url(deconstructed.host):
            self._log(
                safe_add_log, f"Found short URL with {deconstructed.host} in Redis"
            )
            return self._validate_short_url(url, headers)

        # Perform HEAD request, majority of URLs should be okay with this
        response = self._perform_head_request(url, headers, limited_redirects=True)

        # HEAD requests can fail, try heavier GET instead
        if response is None or response.status_code == 404:
            self._log(
                warning_log,
                (
                    "HEAD request failed: " + "response null"
                    if response is None
                    else f"{response.status_code=}"
                ),
            )
            response = self._perform_get_request(url, headers)

        if (
            response.status_code == 404
            and not self._is_cloudfront_error(response.headers)
            and not self._is_accelerator_error(url, response.reason)
        ):
            raise InvalidURLError(
                f"Could not find the given resource at the URL\nurl={url}\nrequest headers={headers}\nresponse headers={response.headers}\nresponse status code={response.status_code}\n"
            )

        # Validates the response from a HEAD or GET request
        location = self._check_for_valid_response_location(url, response)
        if location is not None:
            return location, True

        if response is None or (
            response.status_code >= 400 and response.status_code < 500
        ):
            self._log(
                safe_add_log,
                f"Have to perform wayback check after {response.status_code=}",
            )
            response = self._perform_wayback_check(url, headers)

        if response is None:
            self._log(warning_log, f"1: HEAD/GET/Wayback failed validation for: {url}")
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
        self._log(critical_log, f"2: HEAD/GET/Wayback failed validation for: {url}")
        return url, False

    def _is_cloudfront_error(self, headers: CaseInsensitiveDict) -> bool:
        x_cache = VALIDATION_STRS.X_CACHE
        cf_error = VALIDATION_STRS.ERROR_FROM_CLOUDFRONT
        is_cloudfront_error = (
            x_cache in headers and headers.get(x_cache, "").lower() == cf_error
        )
        self._log(safe_add_log, f"Is cloudfront error: {is_cloudfront_error}")
        return is_cloudfront_error

    def _is_accelerator_error(self, url: str, response_reason: str) -> bool:
        deconstructed_url = deconstruct_url(url)
        is_valid_url = self._validate_host(deconstructed_url.host)
        is_accelerator_error = is_valid_url and "accelerator" in response_reason.lower()

        self._log(safe_add_log, f"Is accelerator error: {is_accelerator_error}")
        return is_accelerator_error

    def _return_url_for_ui_testing(
        self, headers: dict[str, str] | None, url: str
    ) -> tuple[str, bool]:
        invalid_testing_header = "X-U4I-Testing-Invalid"
        if headers and headers.get(invalid_testing_header, "false").lower() == "true":
            raise InvalidURLError("Invalid URL used during test")
        return url, True

    def _filter_out_common_redirect(self, url: str) -> str:
        for common_redirect in COMMON_REDIRECTS:
            if common_redirect in url:
                url = url.removeprefix(common_redirect)
                self._log(
                    safe_add_log, f"Found common direct for URL: {common_redirect}"
                )
                return unquote(url)

        self._log(safe_add_log, "Unable to find common direct for URL")
        return unquote(url)

    @staticmethod
    def generate_random_user_agent() -> str:
        return random.choice(USER_AGENTS)

    @staticmethod
    def has_android_user_agent_and_intent_url(user_agent: str, url: str) -> bool:
        deconstructed = deconstruct_url(url)
        return (
            "android" in user_agent.lower() and deconstructed.scheme.lower() == "intent"
        )


if __name__ == "__main__":
    validator = UrlValidator(is_testing=True)
    INVALID_URLS = (
        "https://www.lowes.com/pd/ReliaBilt-ReliaBilt-3-1-2-in-Zinc-Plated-Flat-Corner-Brace-4-Pack/5003415919",
        "https://www.upgrad.com/blog/top-artificial-intelligence-project-ideas-topics-for-beginners/",
        "www.fnb-online.com/",
        "https://www.fnb-online.com/",
        "https://www.fnb-online.com/personal",
        "https://a.co/d/7jJVnzT",
        "https://immich.app/docs/overview/introduction",
        "https://developers.google.com/calendar/api/guides/overview",
        "https://developers.google.com/keep/api/reference/rest",
        "https://www.lenovo.com/us/en/p/laptops/thinkpad/thinkpadt/thinkpad-t16-gen-2-16-inch-amd/len101t0076#ports_slots",
        "https://www.stackoverflow.com/",
        "yahoo.com",
    )

    print(validator.validate_url(INVALID_URLS[-1]))
    # for invalid_url in INVALID_URLS:
    #    print(validator.validate_url(invalid_url))
    print("Trying to run as script")
