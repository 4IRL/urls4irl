from time import sleep

import pytest

from src.utils import url_validation as url_valid

pytestmark = pytest.mark.unit

valid_urls = {
    "https://www.google.com/": [
        "https://www.google.com/",
        "https://www.google.com",
        "google.com",
        "www.google.com",
        "http://www.google.com",
        "https://www.google.com",
        "https://google.com",
        "ww.google.com",
        "http://google.com",
        "http:/google.com",
        "https:/google.com",
    ],
    "https://www.facebook.com/": [
        "https://www.facebook.com/",
        "https://www.facebook.com",
        "facebook.com",
        "www.facebook.com",
        "http://www.facebook.com",
        "https://facebook.com",
        "ww.facebook.com",
        "http://facebook.com",
        "http:/facebook.com",
        "https:/facebook.com",
    ],
    "https://cherupil.com/": [
        "https://cherupil.com/",
        "https://cherupil.com",
        "cherupil.com",
        "https:/cherupil.com",
        "http://cherupil.com",
        "http:/cherupil.com",
    ],
    "https://www.cherupil.com/": [
        "www.cherupil.com/",
        "www.cherupil.com",
        "https://www.cherupil.com",
        "http://www.cherupil.com/",
        "https:/www.cherupil.com/",
    ],
    "https://flask-limiter.readthedocs.io/en/stable/": [
        "https://flask-limiter.readthedocs.io/",
        "https://flask-limiter.readthedocs.io",
        "http:/flask-limiter.readthedocs.io",
        "https:/flask-limiter.readthedocs.io",
        "https://flask-limiter.readthedocs.io/",
        "http:/flask-limiter.readthedocs.io/",
        "https:/flask-limiter.readthedocs.io/",
        "flask-limiter.readthedocs.io",
        "flask-limiter.readthedocs.io/",
    ],
    "https://stackoverflow.com/": [
        "www.stackoverflow.com",
        "stackoverflow.com",
    ],
}

invalid_urls = (
    "w.google.com",
    "http://mw1.google.com/mw-earth-vectordb/kml-samples/gp/seattle/gigapxl/$[level]/r$[y]_c$[x].jpg",
    "http://www.example.com/main.html",
    "/main.html",
    "http:\\www.example.com\\andhere.html",
)

urls_needing_valid_user_agent = {
    "https://www.homedepot.com/c/ah/how-to-build-a-bookshelf/9ba683603be9fa5395fab904e329862",
    "https://www.lenovo.com/us/en/p/laptops/thinkpad/thinkpadt/thinkpad-t16-gen-2-(16-inch-amd)/len101t0076#ports_slots",
}


def test_valid_urls():
    """
    GIVEN valid URLs and their known final URL locations
    WHEN the url validation functions checks these URLs
    THEN ensure each variant of the URL outputs the identical and correct URL to use
    """
    for valid_url in valid_urls:
        urls_to_check = valid_urls[valid_url]
        for url in urls_to_check:
            commonized_url = url_valid.find_common_url(url)
            assert valid_url == commonized_url


def test_invalid_urls():
    """
    GIVEN invalid URLs
    WHEN the url validation functions checks these invalid URLs
    THEN ensure the InvalidURLError exception is raised
    """
    for invalid_url in invalid_urls:
        with pytest.raises(url_valid.InvalidURLError):
            url_valid.find_common_url(invalid_url)


def test_urls_requiring_valid_user_agent():
    """
    GIVEN URLs that seemed to fail unknowingly, but were due to the request
        failing due to a User-agent indicating a script, OR the returns
        with a different URL even with a 200 status (lenovo)
    WHEN the url validation function checks these URLs
    THEN ensure that these urls are now validated properly
    """
    for unknown_url in urls_needing_valid_user_agent:
        validated_url = False
        for _ in range(3):
            if unknown_url == url_valid.find_common_url(unknown_url):
                validated_url = True
                break
            sleep(0.1)
        assert validated_url


def test_random_user_agents():
    """
    GIVEN URLs that seemed to fail unknowingly, but were due to the request
        failing due to a User-agent indicating a script
    WHEN the User-Agent is iterated through random values
    THEN ensure that these urls are now validated properly
    """
    valid_agent_used = 0
    for unknown_url in urls_needing_valid_user_agent:
        for user_agent in set(url_valid.USER_AGENTS):
            if unknown_url == url_valid.find_common_url(unknown_url, user_agent):
                valid_agent_used += 1
                break

            # Avoid any kind of rate limiting or semblance of being a bot
            sleep(0.1)

    assert valid_agent_used == len(urls_needing_valid_user_agent)
