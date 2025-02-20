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
from urllib.parse import unquote

import redis
from redis.client import Redis
from requests.structures import CaseInsensitiveDict
from url_normalize import url_normalize
from url_normalize.tools import deconstruct_url

from flask import Flask


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

    def init_app(self, app: Flask) -> None:
        app.extensions[VALIDATION_STRS.URL_VALIDATION_MODULE] = self
        is_testing: bool = app.config.get("TESTING", False)
        is_production: bool = app.config.get("PRODUCTION", False)
        is_ui_testing: bool = app.config.get("UI_TESTING", False)
        is_not_production_and_is_testing_ui = (
            not is_production and is_testing and is_ui_testing
        )
        self._ui_testing: bool = is_not_production_and_is_testing_ui
        self._redis_uri = app.config.get(ENV.REDIS_URI, None)
        self._is_testing = is_testing

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

        invalid_headers = (
            VALIDATION_STRS.CONTENT_TYPE,
            VALIDATION_STRS.X_REQUESTED_WITH,
            VALIDATION_STRS.X_CSRF_TOKEN,
            VALIDATION_STRS.CONTENT_LENGTH,
            VALIDATION_STRS.COOKIE,
            VALIDATION_STRS.ORIGIN,
            VALIDATION_STRS.REFERER,
        )

        for invalid_header in invalid_headers:
            if invalid_header in headers:
                headers.pop(invalid_header)

        headers[VALIDATION_STRS.HOST] = deconstruct_url(url).host
        return headers

    def _perform_head_request(
        self, url: str, headers: dict[str, str], limited_redirects: bool = False
    ) -> requests.Response | None:
        try:
            if limited_redirects:
                response = self._perform_head_with_custom_redirect(url, headers)
            else:
                response = self._perform_head_with_no_redirects(url, headers)

        except requests.exceptions.ReadTimeout:
            return None

        except requests.exceptions.TooManyRedirects:
            return self._perform_head_request(url, headers, limited_redirects=False)

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

    def _perform_head_with_custom_redirect(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response | None:
        max_num_redirects = 10
        num_redirects = 0

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
                return None

            redirect_url = response.headers.get(VALIDATION_STRS.LOCATION, "")
            if (
                deconstruct_url(redirect_url).scheme != "https"
                and response.next
                and response.next.url
                and deconstruct_url(response.next.url).scheme == "https"
            ):
                redirect_url = response.next.url
            else:
                return None

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

        return response

    def _perform_head_with_no_redirects(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response | None:
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
            return None
        return response

    def _perform_get_request(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        try:
            response = self._perform_get_with_custom_redirect(url, headers)

        except requests.exceptions.ReadTimeout:
            return self._all_user_agent_sampling(url, headers)

        except requests.exceptions.ConnectionError as e:
            raise InvalidURLError("Unable to connect to the given URL. " + str(e))

        except requests.exceptions.MissingSchema as e:
            raise InvalidURLError("Invalid schema for this URL. " + str(e))

        except requests.exceptions.TooManyRedirects as e:
            raise InvalidURLError("Too many redirects for this URL. " + str(e))

        else:
            return response

    def _perform_get_with_custom_redirect(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        max_num_redirects = 10
        num_redirects = 0

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
            if num_redirects >= max_num_redirects or response.status_code in range(
                400, 600
            ):
                return response

            redirect_url = response.headers.get(VALIDATION_STRS.LOCATION, "")

            # Check for proper schema, some responses include a relative URL in the LOCATION header
            # so that needs to be checked here as well
            if (
                deconstruct_url(redirect_url).scheme != "https"
                and response.next
                and response.next.url
                and deconstruct_url(response.next.url).scheme == "https"
            ):
                redirect_url = response.next.url

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

        return response

    def _all_user_agent_sampling(
        self, url: str, headers: dict[str, str]
    ) -> requests.Response:
        for agent in USER_AGENTS:
            try:
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
                    raise InvalidURLError("Unable to validate URL within 30 seconds.")
                continue
            except requests.exceptions.ConnectionError as e:
                raise InvalidURLError("Unable to connect to the given URL. " + str(e))
            except requests.exceptions.MissingSchema as e:
                raise InvalidURLError("Invalid schema for this URL. " + str(e))
            except requests.exceptions.TooManyRedirects as e:
                raise InvalidURLError("Too many redirects for this URL. " + str(e))
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
                    raise WaybackRateLimited("Too many attempts, please wait a minute.")

                wayback_url = VALIDATION_STRS.WAYBACK_ARCHIVE + str(year) + "/" + url
                wayback_archive_response = self._perform_head_request(
                    wayback_url,
                    headers,
                )
                if wayback_archive_response is None:
                    continue

                wayback_status_code = wayback_archive_response.status_code
                if wayback_status_code not in range(200, 400):
                    continue

                if 300 <= wayback_status_code < 400:
                    is_rate_limited = redis_client and self._is_wayback_rate_limited(
                        redis_client
                    )
                    if is_rate_limited:
                        raise WaybackRateLimited(
                            "Too many attempts, please wait a minute."
                        )
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

        except requests.exceptions.ConnectionError:
            raise WaybackRateLimited("Too many attempts, please wait a minute.")

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
                location = self._filter_out_common_redirect(url)

            deconstructed = deconstruct_url(location)

            # Check for proper schema
            if deconstructed.scheme == "https":
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
            return self._filter_out_common_redirect(url)

        # Check for proper schema
        if location is not None and deconstruct_url(location).scheme != "https":
            return None

        return location

    def _check_if_is_short_url(self, url_domain: str) -> bool:
        if not self._redis_uri or self._redis_uri == "memory://":
            return False

        redis_client: Redis = redis.Redis.from_url(self._redis_uri)  # type: ignore
        return redis_client.sismember(VALIDATION_STRS.SHORT_URLS, url_domain) == 1

    def _validate_short_url(
        self, url: str, headers: dict[str, str]
    ) -> Tuple[str, bool]:
        MAX_RETRY_ATTEMPTS = 5
        try:
            for _ in range(MAX_RETRY_ATTEMPTS):
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
                        return response.next.url, True

                    if VALIDATION_STRS.LOCATION in response.headers:
                        return response.headers[VALIDATION_STRS.LOCATION], True

        except requests.exceptions.ReadTimeout as e:
            raise InvalidURLError("Timed out trying to read this short URL. " + str(e))
        except requests.exceptions.ConnectionError as e:
            raise InvalidURLError("Unable to connect to the short URL. " + str(e))
        except requests.exceptions.MissingSchema as e:
            raise InvalidURLError("Invalid schema for this short URL. " + str(e))
        except requests.RequestException as e:
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
        deconstructed = deconstruct_url(url)

        # Check for proper schema
        if deconstructed.scheme != "https":
            raise InvalidURLError("Improper scheme given for this URL")

        # Return during UI testing here so we can check ill-formed URLs and behavior on frontend
        if self._ui_testing:
            return self._return_url_for_ui_testing(user_headers, url)

        # DNS Check to ensure valid domain and host
        if not self._validate_host(deconstructed.host):
            raise InvalidURLError("Domain did not resolve into a valid IP address")

        # Build headers to perform HTTP request to validate URL
        headers = self._generate_headers(url, user_headers)

        # Check if contained within short URL domains
        if self._check_if_is_short_url(deconstructed.host):
            return self._validate_short_url(url, headers)

        # Perform HEAD request, majority of URLs should be okay with this
        response = self._perform_head_request(url, headers, limited_redirects=True)

        # HEAD requests can fail for shortened URLs, try GET just in case
        if response is None or response.status_code == 404:
            response = self._perform_get_request(url, headers)

        if response.status_code == 404 and not self._is_cloudfront_error(
            response.headers
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

    def _is_cloudfront_error(self, headers: CaseInsensitiveDict) -> bool:
        x_cache = VALIDATION_STRS.X_CACHE
        cf_error = VALIDATION_STRS.ERROR_FROM_CLOUDFRONT
        return x_cache in headers and headers.get(x_cache, "").lower() == cf_error

    def _return_url_for_ui_testing(
        self, headers: dict[str, str] | None, url: str
    ) -> tuple[str, bool]:
        invalid_testing_header = "X-U4I-Testing-Invalid"
        if headers and headers.get(invalid_testing_header, "false").lower() == "true":
            raise InvalidURLError("Invalid URL used during test")
        return url, True

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
    )

    print(validator.validate_url(INVALID_URLS[-1]))
    # for invalid_url in INVALID_URLS:
    #    print(validator.validate_url(invalid_url))
    print("Trying to run as script")
