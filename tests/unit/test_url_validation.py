from urls4irl.utils import url_validation as url_valid
from pytest import raises

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
    "https://www.lenovo.com/us/en/p/laptops/thinkpad/thinkpadt/thinkpad-t16-gen-2-(16-inch-amd)/len101t0076#ports_slots"
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
            assert valid_url == url_valid.check_request_head(url)


def test_invalid_urls():
    """
    GIVEN invalid URLs
    WHEN the url validation functions checks these invalid URLs
    THEN ensure the InvalidURLError exception is raised
    """
    for invalid_url in invalid_urls:
        with raises(url_valid.InvalidURLError):
            url_valid.check_request_head(invalid_url)


def test_urls_requiring_valid_user_agent():
    """
    GIVEN URLs that seemed to fail unknowingly, but were due to the request
        failing due to a User-agent indicating a script
    WHEN the url validation function checks these URLs
    THEN ensure that these urls are now validated properly
    """
    for unknown_url in urls_needing_valid_user_agent:
        assert unknown_url == url_valid.check_request_head(unknown_url)
