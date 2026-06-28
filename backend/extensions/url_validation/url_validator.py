"""
Parses a URL to verify it matches the WHATWG URL spec, via the `ada_url` library..
Spec: https://url.spec.whatwg.org/

If URL does not contain a scheme, presumptively prepends 'https://'.

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

import ipaddress
import re

import ada_url
from flask import Flask

if __name__ == "__main__":
    # TODO: Change imports when running as standalone module
    from utils.strings.url_validation_strs import URL_VALIDATION as VALIDATION_STRS

    critical_log = None
    error_log = None
    info_log = None
    safe_add_log = None
    safe_add_many_logs = None
    warning_log = None

    from extensions.url_validation.constants import (
        CORE_SCHEMES,
        DEV_URLS,
        HOSTNAME,
        HREF,
        INVALID_SCHEME_PREFIXES,
        OTHER_VALID_SCHEMES,
        PROTOCOL,
        TRACKING_QUERY_PARAMS,
        TRACKING_QUERY_PARAM_PREFIXES,
        WEB_SCHEMES_FOR_TRACKING_STRIP,
    )

else:
    from backend.utils.strings.url_validation_strs import (
        URL_VALIDATION as VALIDATION_STRS,
    )
    from backend.app_logger import safe_add_log, warning_log, critical_log
    from backend.extensions.url_validation.constants import (
        CORE_SCHEMES,
        DEV_URLS,
        HOSTNAME,
        HREF,
        INVALID_SCHEME_PREFIXES,
        OTHER_VALID_SCHEMES,
        PROTOCOL,
        TRACKING_QUERY_PARAMS,
        TRACKING_QUERY_PARAM_PREFIXES,
        WEB_SCHEMES_FOR_TRACKING_STRIP,
    )


class AdaUrlParsingError(Exception):
    """Error in validating URL."""

    pass


class InvalidURLError(Exception):
    """Error in validating URL."""

    pass


class URLWithCredentialsError(InvalidURLError):
    """Error if the URL contains credentials and is not mailto."""

    pass


class UrlValidator:
    def __init__(self, skip_logs: bool = False) -> None:
        self._has_app = False
        self._skip_logs = skip_logs
        self.scheme_regex = re.compile(r"^([a-z][a-z0-9+.-]*):(.*)$")
        self.host_and_port_regex = re.compile(r"^([^:]+):(\d{1,5})(.*)$")

    def init_app(self, app: Flask) -> None:
        app.extensions[VALIDATION_STRS.URL_VALIDATION_MODULE] = self
        is_testing: bool = app.config.get("TESTING", False)
        is_production: bool = app.config.get("PRODUCTION", False)
        is_ui_testing: bool = app.config.get("UI_TESTING", False)
        is_debug: bool = app.config.get("FLASK_DEBUG", False)
        self._has_app = is_testing or is_production or is_ui_testing or is_debug

    def _log(self, log_fn, log):
        log_fn(log) if self._has_app and not self._skip_logs else None

    def normalize_url(self, url: str | None) -> str:
        """
        Normalizes a URL which will still need to be validated.
        Normalization involves:
        1) Removing leading/trailing whitespace/tabs

        Then a lowercased URL is checked.
        If a host and numeric port are found in the URL, prefix http if DEV scheme else https

        The scheme of the URL is parsed with a regex:
        1) If no scheme is found: prepend http if not a localhost URL, else https
        2) If scheme is found that is invalid, raise InvalidURLError
        3) If scheme is found that is a dev URL, prepend http
        4) If scheme not in scheme whitelist, raise InvalidURLError
        5) If scheme does not start with mailto, contains an @, most likely of the format
            user:pass@example.com - We deny these here.
        5) Otherwise, return the normalized URL as it contains a valid white-listed scheme

        Args:
            url (str): The URL to normalize

        Returns:
            (str): The normalized URL to validate
        """
        self._log(safe_add_log, log=f"Validating {url}")

        if not url:
            self._log(warning_log, "Empty URL passed to backend")
            raise InvalidURLError("URL cannot be empty")

        normalized_url = (
            url.replace("\\t", "\t").replace("\\n", "\n").replace("\\r", "\r")
        ).strip()

        lowercased_url = normalized_url.lower()

        host_and_port_match = re.match(self.host_and_port_regex, lowercased_url)
        if host_and_port_match is not None:
            host = host_and_port_match.group(1)
            port = host_and_port_match.group(2)

            if 1 <= int(port) <= 65535:
                prefix = "http://" if host.startswith(DEV_URLS) else "https://"
                return prefix + lowercased_url

        scheme_match = re.match(self.scheme_regex, lowercased_url)

        # Verify if the URL contains ANY scheme, and if not, prepend https://
        if scheme_match is None:
            prefix = "http://" if lowercased_url.startswith(DEV_URLS) else "https://"
            normalized_url = normalized_url.lstrip("/")
            return prefix + normalized_url

        scheme = scheme_match.group(1)

        if scheme.startswith(INVALID_SCHEME_PREFIXES):
            self._log(
                warning_log,
                f"Invalid URL scheme during normalization: {normalized_url}",
            )
            raise InvalidURLError("URL scheme is invalid")

        if scheme.startswith(DEV_URLS):
            return "http://" + normalized_url

        if scheme not in CORE_SCHEMES | OTHER_VALID_SCHEMES:
            self._log(warning_log, f"Unknown scheme not registered: {normalized_url}")
            raise InvalidURLError("URL scheme unknown")

        if scheme != "mailto" and self._has_user_pass_type_url(normalized_url):
            self._log(warning_log, "URL with credentials blocked")
            raise URLWithCredentialsError("URLs with credentials not allowed")

        return normalized_url

    @staticmethod
    def _is_tracking_param(param_name: str) -> bool:
        """
        Returns True if a query-parameter name is a known marketing/advertising
        tracking parameter that is safe to strip from a URL.

        Matching is case-insensitive and covers both the exact-name blocklist
        (`TRACKING_QUERY_PARAMS`) and the open-ended prefix families
        (`TRACKING_QUERY_PARAM_PREFIXES`, e.g. the `utm_*` family).

        Examples:
            "utm_source" -> True
            "GCLID"      -> True
            "q"          -> False
        """
        lowered = param_name.lower()
        return lowered in TRACKING_QUERY_PARAMS or lowered.startswith(
            TRACKING_QUERY_PARAM_PREFIXES
        )

    def _strip_tracking_params(self, href: str) -> str:
        """
        Removes known marketing/advertising tracking query params from a URL,
        preserving all non-tracking params and their original order/repeats.

        Example:
            "https://x.com/p?utm_source=g&q=1&fbclid=z" -> "https://x.com/p?q=1"
        """
        search = ada_url.URL(href).search
        if not search:
            return href

        params = ada_url.URLSearchParams(search.lstrip("?"))
        tracking_keys = [
            key for key, _ in params.items() if self._is_tracking_param(key)
        ]
        # No tracking params present: return the href untouched so that the
        # original query-string encoding (e.g. "%20" vs "+", literal "://") is
        # preserved rather than being re-serialized by URLSearchParams.
        if not tracking_keys:
            return href

        for key in tracking_keys:
            params.delete(key)

        new_search = str(params)
        return ada_url.replace_url(href, search=new_search)

    def contains_tracking_params(self, url: str) -> bool:
        """
        Returns True if a URL contains any known marketing/advertising tracking
        query param. Best-effort metric signal only: never raises — any parse
        failure yields False.

        Example:
            "https://x.com/p?utm_source=g" -> True
            "https://x.com/p?q=1"          -> False
        """
        try:
            search = ada_url.URL(url).search
            return any(
                self._is_tracking_param(key)
                for key, _ in ada_url.URLSearchParams(search.lstrip("?")).items()
            )
        # Broad catch is intentional: this produces a best-effort metric signal
        # only and must never raise into the request path.
        except Exception:
            return False

    def _has_user_pass_type_url(self, normalized_url: str) -> bool:
        """
        To prevent user's leaked credentials, block any type of user:pass@example.com URLs.

        Args:
            url (str): The URL to normalize

        Returns:
            (bool): True if is a user:pass@example.com type URL
        """
        if "@" not in normalized_url or ":" not in normalized_url:
            return False

        potential_scheme_and_user_pass = normalized_url.split("@")[0]

        if "://" in potential_scheme_and_user_pass:
            potential_scheme_and_user_pass = potential_scheme_and_user_pass.split(
                "://"
            )[-1]

        if ":" in potential_scheme_and_user_pass:
            return True

        return False

    def _has_valid_domain(self, domain: str) -> bool:
        """
        Verifies whether the given domain has is in the format of X.YZ by implementing the following heuristics:

        1) The domain must have at least one period
        2) The top level domain (TLD) must be at least two characters long

        Args:
            domain (str): Current domain of the URL

        Returns:
            True if domain is valid, False otherwise
        """

        # Localhost is an exception to the heuristics mentioned
        if domain in ("localhost", "[::1]") or domain.startswith("localhost:"):
            return True

        # IP addresses are valid domains that don't have a TLD
        try:
            ipaddress.ip_address(domain)
            return True
        except ValueError:
            pass

        # ICANN states at least 2 ASCII characters besides the period
        # https://newgtlds.icann.org/en/applicants/global-support/faqs/faqs-en
        if "." not in domain or len(domain) < 3:
            return False

        parts = domain.split(".")
        tld = parts[-1]

        return len(tld) >= 2

    def validate_url(self, normalized_url: str) -> str:
        if not ada_url.check_url(normalized_url):
            self._log(
                warning_log,
                f"Invalid URL passed to validate in check_url: {normalized_url}",
            )
            raise InvalidURLError("URL is invalid")

        try:
            parsed_url = ada_url.parse_url(
                normalized_url,
                attributes=(
                    PROTOCOL,
                    HOSTNAME,
                    HREF,
                ),
            )

        except ValueError:
            self._log(
                warning_log,
                f"Invalid URL passed to validate via parse_url: {normalized_url}",
            )
            raise InvalidURLError("URL could not be parsed")

        scheme = parsed_url.get(PROTOCOL)
        if not scheme or scheme.startswith(INVALID_SCHEME_PREFIXES):
            self._log(
                critical_log, f"Invalid URL scheme during validation: {normalized_url}"
            )
            raise InvalidURLError("Invalid URL protocol during validation")

        if scheme.rstrip(":") not in CORE_SCHEMES | OTHER_VALID_SCHEMES:
            self._log(
                critical_log,
                f"Non-whitelisted scheme during validation: {normalized_url}",
            )
            raise InvalidURLError("Invalid URL protocol during validation")

        hostname = parsed_url.get(HOSTNAME)
        if scheme.startswith("http") and (
            not hostname or not self._has_valid_domain(hostname)
        ):
            self._log(
                warning_log, f"User provided invalid hostname URL: {normalized_url}"
            )
            raise InvalidURLError(f"Invalid URL hostname: {hostname}")

        validated_ada_url_href = parsed_url.get(HREF, None)
        if not validated_ada_url_href:
            self._log(
                critical_log,
                f"URL could not be serialized using ada-url: {normalized_url}",
            )
            raise AdaUrlParsingError(f"Invalid URL hostname: {hostname}")

        validated_ada_url = ada_url.URL(validated_ada_url_href)

        final_ada_url = (
            ada_url.replace_url(
                validated_ada_url_href, host=validated_ada_url.host.lower()
            )
            if validated_ada_url.host
            else validated_ada_url_href
        )

        if scheme.rstrip(":") in WEB_SCHEMES_FOR_TRACKING_STRIP:
            final_ada_url = self._strip_tracking_params(final_ada_url)

        return final_ada_url


if __name__ == "__main__":
    validator = UrlValidator(skip_logs=True)

    URLS = (
        (
            "mailto:USER@EXAMPLE.COM",
            "MAILTO:USER@EXAMPLE.COM",
        ),
        (
            "news:COMP.LANG.PYTHON",
            "NEWS:COMP.LANG.PYTHON",
        ),
        (
            "https://api.github.com/users/TEST",
            "https://API.GITHUB.COM/users/TEST",
        ),
        (
            "https://api.github.com/users/TEST",
            "\n HTTPS://API.GITHUB.COM/users/TEST \n",
        ),
        (
            "http://example.com/PATH/TO/Resource",
            "HTTP://Example.COM/PATH/TO/Resource",
        ),
        (
            "https://api.example.org/Users",
            "API.EXAMPLE.ORG/Users",
        ),
    )

    for should_be, is_url in URLS:
        normalized = validator.normalize_url(is_url)
        validated = validator.validate_url(normalized)

        if should_be != validated:
            continue
