import pytest

from backend.extensions.metrics.ua_classifier import classify_user_agent
from backend.metrics.events import DeviceType

pytestmark = pytest.mark.unit


_IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
_IPAD_UA = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
_PIXEL_7_ANDROID_CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)
_WINDOWS_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_MAC_SAFARI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15"
)
_LINUX_FIREFOX_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
)


def test_classify_user_agent_iphone_returns_mobile():
    assert classify_user_agent(_IPHONE_UA) == DeviceType.MOBILE


def test_classify_user_agent_ipad_returns_mobile():
    assert classify_user_agent(_IPAD_UA) == DeviceType.MOBILE


def test_classify_user_agent_pixel_7_android_chrome_returns_mobile():
    assert classify_user_agent(_PIXEL_7_ANDROID_CHROME_UA) == DeviceType.MOBILE


def test_classify_user_agent_windows_chrome_returns_desktop():
    assert classify_user_agent(_WINDOWS_CHROME_UA) == DeviceType.DESKTOP


def test_classify_user_agent_mac_safari_returns_desktop():
    assert classify_user_agent(_MAC_SAFARI_UA) == DeviceType.DESKTOP


def test_classify_user_agent_linux_firefox_returns_desktop():
    assert classify_user_agent(_LINUX_FIREFOX_UA) == DeviceType.DESKTOP


def test_classify_user_agent_empty_string_returns_desktop():
    assert classify_user_agent("") == DeviceType.DESKTOP


def test_classify_user_agent_none_returns_desktop():
    assert classify_user_agent(None) == DeviceType.DESKTOP
