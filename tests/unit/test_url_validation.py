import ada_url
import pytest

from src.extensions.url_validation.url_validator import (
    InvalidURLError,
    UrlValidator,
)
from src.extensions.url_validation import constants as url_constants

pytestmark = pytest.mark.unit

VALID_MOCK_URLS_FOR_NORMALIZE = {
    "https://example.com": [
        "https://example.com",
        "HTTPS://EXAMPLE.COM",
        " https://example.com",
        "https://example.com ",
        " https://example.com ",
        "  HTTPS://EXAMPLE.COM  ",
        "\thttps://example.com\t",
        "example.com",
        "EXAMPLE.COM",
        " example.com",
        "example.com ",
        " example.com ",
        "  EXAMPLE.COM  ",
        "\texample.com\t",
        "\nexample.com\n",
    ],
    "http://www.google.com": [
        "HTTP://WWW.GOOGLE.COM",
        "  http://www.google.com  ",
    ],
    "https://www.google.com": [
        "https://www.google.com",
        "HTTPS://www.google.com",
        "www.google.com",
        "WWW.GOOGLE.COM",
        "  www.google.com  ",
        " WWW.GOOGLE.COM ",
        "  WWW.Google.COM  ",
    ],
    "https://www.github.com": [
        "www.github.com",
        "WWW.GITHUB.COM",
        "  WWW.GITHUB.COM  ",
    ],
    "https://github.com": [
        "https://github.com",
        "\thttps://github.com\t",
        "github.com",
        "GITHUB.COM",
    ],
    "https://api.github.com": [
        "https://api.github.com",
        "api.github.com",
        "API.GITHUB.COM",
        " api.github.com ",
        "  API.GITHUB.COM  ",
    ],
    "http://example.com": [
        "http://example.com",
        "HTTP://EXAMPLE.COM",
        " http://example.com ",
        "  HTTP://EXAMPLE.COM  ",
        " HTTP://Example.COM ",
    ],
    "ftp://files.example.com": [
        "ftp://files.example.com",
        "FTP://FILES.EXAMPLE.COM",
        " ftp://files.example.com ",
        "  FTP://FILES.EXAMPLE.COM  ",
    ],
    "ftp://ftp.example.com": [
        "ftp://ftp.example.com",
        "FTP://ftp.example.com",
    ],
    "http://localhost:8080": [
        "http://localhost:8080",
        "HTTP://LOCALHOST:8080",
        " http://localhost:8080 ",
        "localhost:8080",
        "LOCALHOST:8080",
        " localhost:8080 ",
        "  LOCALHOST:8080  ",
    ],
    "https://localhost:8080": [
        "https://localhost:8080",
        "HTTPS://LOCALHOST:8080",
        " https://localhost:8080 ",
        "  HTTPS://LOCALHOST:8080  ",
    ],
    "https://192.168.1.1:3000": [
        "https://192.168.1.1:3000",
        " https://192.168.1.1:3000 ",
        "192.168.1.1:3000",
        " 192.168.1.1:3000 ",
        "  192.168.1.1:3000  ",
    ],
    "https://example.com:443": [
        "https://example.com:443",
        "HTTPS://EXAMPLE.COM:443",
        " https://example.com:443 ",
        "example.com:443",
        "EXAMPLE.COM:443",
        " example.com:443 ",
        "  EXAMPLE.COM:443  ",
    ],
    "https://example.com/path": [
        "https://example.com/path",
        "HTTPS://EXAMPLE.COM/path",
        " https://example.com/path ",
        "example.com/path",
        "EXAMPLE.COM/path",
        " example.com/path ",
        "  EXAMPLE.COM/path  ",
    ],
    "https://api.github.com/users": [
        "https://api.github.com/users",
        " https://api.github.com/users ",
        "api.github.com/users",
        "API.GITHUB.COM/users",
        " api.github.com/users ",
    ],
    "https://example.com/path/to/resource": [
        "https://example.com/path/to/resource",
        " https://example.com/path/to/resource ",
        "example.com/path/to/resource",
        " example.com/path/to/resource ",
        "  example.com/path/to/resource  ",
    ],
    "https://example.com/api/v1/users": [
        "https://example.com/api/v1/users",
        "example.com/api/v1/users",
    ],
    "https://example.com/complex/path/with/multiple/segments": [
        "https://example.com/complex/path/with/multiple/segments",
        "example.com/complex/path/with/multiple/segments",
    ],
    "http://example.com/api/v1/users?id=123": [
        "http://example.com/api/v1/users?id=123",
    ],
    "https://example.com/api/v1/users?id=123": [
        "https://example.com/api/v1/users?id=123",
        "example.com/api/v1/users?id=123",
    ],
    "https://example.com/search?q=test&sort=date": [
        "https://example.com/search?q=test&sort=date",
        "example.com/search?q=test&sort=date",
    ],
    "http://example.com/search?q=hello%20world": [
        "http://example.com/search?q=hello%20world",
    ],
    "https://example.com/search?q=hello%20world": [
        "https://example.com/search?q=hello%20world",
        "example.com/search?q=hello%20world",
    ],
    "https://example.com/search?q=HELLO%20world": [
        "https://example.com/search?q=HELLO%20world",
        "example.com/search?q=HELLO%20world",
    ],
    "http://example.com/query?param=": [
        "http://example.com/query?param=",
    ],
    "https://example.com/query?param=": [
        "https://example.com/query?param=",
        "example.com/query?param=",
    ],
    "https://example.com?": ["https://example.com?", "example.com?"],
    "https://example.com/page#section1": [
        "https://example.com/page#section1",
        "example.com/page#section1",
    ],
    "https://example.com/path?query=value#fragment": [
        "https://example.com/path?query=value#fragment",
        "example.com/path?query=value#fragment",
    ],
    "https://example.com/path%20with%20spaces": [
        "https://example.com/path%20with%20spaces",
        "example.com/path%20with%20spaces",
    ],
    "https://example.com/path/with-dashes": [
        "https://example.com/path/with-dashes",
        "example.com/path/with-dashes",
    ],
    "http://example.com/path_with_underscores": [
        "http://example.com/path_with_underscores",
    ],
    "https://example.com/path_with_underscores": [
        "https://example.com/path_with_underscores",
        "example.com/path_with_underscores",
    ],
    "https://example.com/path/with.dots": [
        "https://example.com/path/with.dots",
        "example.com/path/with.dots",
    ],
    "https://example.com/": ["https://example.com/", "example.com/"],
    "http://example.com//double//slash": ["http://example.com//double//slash"],
    "https://example.com/path/../other": [
        "https://example.com/path/../other",
        "example.com/path/../other",
    ],
    "http://example.com/path/./current": ["http://example.com/path/./current"],
    # Different ports
    "http://example.com:80/default-port": ["http://example.com:80/default-port"],
    "https://example.com:443/default-https-port": [
        "https://example.com:443/default-https-port",
        "example.com:443/default-https-port",
    ],
    # IPv6 and special cases
    "http://[::1]:8080/ipv6-localhost": ["http://[::1]:8080/ipv6-localhost"],
    "https://xn--e1afmkfd.xn--p1ai/": [
        "https://xn--e1afmkfd.xn--p1ai/",
        "xn--e1afmkfd.xn--p1ai/",
    ],
    # Special schemes (should remain unchanged except case)
    "sftp://example.com": [
        "sftp://example.com",
        "SFTP://EXAMPLE.COM",
        " sftp://example.com ",
    ],
    "ssh://example.com": ["ssh://example.com", "SSH://EXAMPLE.COM"],
    "mailto:user@example.com": ["mailto:user@example.com", "MAILTO:user@example.com"],
    "mailto:USER@EXAMPLE.COM": ["mailto:USER@EXAMPLE.COM", "MAILTO:USER@EXAMPLE.COM"],
    "tel:+1234567890": ["tel:+1234567890", "TEL:+1234567890"],
    "sms:+1234567890": ["sms:+1234567890", "SMS:+1234567890"],
    "ldap://directory.example.com": [
        "ldap://directory.example.com",
        "LDAP://DIRECTORY.EXAMPLE.COM",
    ],
    "news:comp.lang.python": ["news:comp.lang.python", "NEWS:comp.lang.python"],
    "news:COMP.LANG.PYTHON": ["news:COMP.LANG.PYTHON", "NEWS:COMP.LANG.PYTHON"],
    "gopher://gopher.example.com": [
        "gopher://gopher.example.com",
        "GOPHER://GOPHER.EXAMPLE.COM",
    ],
    "https://a.co": ["https://a.co", "a.co", "A.CO", " a.co "],
    "https://x.y.z.example.com": [
        "https://x.y.z.example.com",
        "x.y.z.example.com",
        "X.Y.Z.EXAMPLE.COM",
    ],
    "https://sub.sub.sub.example.com/long/path": [
        "https://sub.sub.sub.example.com/long/path",
        "sub.sub.sub.example.com/long/path",
        "SUB.SUB.SUB.EXAMPLE.COM/long/path",
    ],
    "https://example-with-dashes.com": [
        "https://example-with-dashes.com",
        "example-with-dashes.com",
        "EXAMPLE-WITH-DASHES.COM",
    ],
    "https://example_with_underscores.com": [
        "https://example_with_underscores.com",
        "example_with_underscores.com",
        "EXAMPLE_WITH_UNDERSCORES.COM",
    ],
    "https://123.example.com": [
        "https://123.example.com",
        "123.example.com",
        "123.EXAMPLE.COM",
    ],
    "https://example123.com": [
        "https://example123.com",
        "example123.com",
        "EXAMPLE123.COM",
    ],
    "http://subdomain.example.org": [
        "HTTP://SubDomain.Example.oRg",
        "http://subdomain.example.org",
    ],
    "https://subdomain.example.org": [
        "https://subdomain.example.org",
        "subdomain.example.org",
        "SUBDOMAIN.EXAMPLE.ORG",
        " subdomain.example.org ",
    ],
    "https://mail.example.com": [
        "https://mail.example.com",
        "mail.example.com",
        "MAIL.EXAMPLE.COM",
    ],
    "https://cdn.example.com/assets": [
        "https://cdn.example.com/assets",
        "cdn.example.com/assets",
        "CDN.EXAMPLE.COM/assets",
    ],
    # Mixed complex cases
    "https://api.github.com/users/test": [
        "https://API.GITHUB.COM/users/test",
        "\n HTTPS://API.GITHUB.COM/users/test \n",
    ],
    "https://api.github.com/users/TEST": [
        "https://API.GITHUB.COM/users/TEST",
        "\n HTTPS://API.GITHUB.COM/users/TEST \n",
    ],
    "http://example.com/PATH/TO/Resource": ["HTTP://Example.COM/PATH/TO/Resource"],
    "http://example.com/path/TO/RESOURCE": ["HTTP://Example.COM/path/TO/RESOURCE"],
    "http://example.com/path/to/resource": ["HTTP://Example.COM/path/to/resource"],
    "https://api.example.org/users": [
        " API.EXAMPLE.ORG/users ",
    ],
    "https://api.example.org/Users": [
        " API.EXAMPLE.ORG/Users ",
    ],
    "https://example.com/?continue=https://gogle.cm": [
        "https://example.com/?continue=https://gogle.cm",
        "example.com/?continue=https://gogle.cm",
        "EXAMPLE.com/?continue=https://gogle.cm",
        "example.COM/?continue=https://gogle.cm",
    ],
}

URLS_WITH_DIFFERENT_PATH = {
    "https://example.com/?continue=https://gogle.cm": [
        "https://example.com/?CONTINUE=https://gogle.cm",
        "https://example.com/?continue=HTTPS://gogle.cm",
        "https://example.com/?continue=https://GOGLE.cm",
    ],
    "https://example.com/page.html": [
        "https://example.com/Page.html",
        "https://example.com/PAge.html",
        "https://example.com/PAGe.html",
        "https://example.com/PAGE.html",
    ],
    "https://example.com/api?id=123": [
        "https://example.com/api?Id=123",
        "https://example.com/api?iD=123",
        "https://example.com/api?ID=123",
    ],
    "https://example.com/api/path/one": [
        "https://example.com/API/path/one",
        "https://example.com/api/PATH/one",
        "https://example.com/api/path/ONE",
    ],
}

VALID_MOCK_URLS_FOR_VALIDATE = VALID_MOCK_URLS_FOR_NORMALIZE.keys()

FLATTENED_NORMALIZED_AND_INPUT_VALID_URLS = [
    (valid_url, input_url)
    for valid_url, urls in VALID_MOCK_URLS_FOR_NORMALIZE.items()
    for input_url in urls
]

FLATTENED_URLS_WITH_DIFFERENT_PATH = [
    (lowercase_url, valid_url)
    for lowercase_url, urls in URLS_WITH_DIFFERENT_PATH.items()
    for valid_url in urls
]

INVALID_MOCK_URLS_FOR_NORMALIZED = (
    "javascript:alert(1)",
    "javascript:console.log('hi')",
    "javascript:document.cookie",
    "javascript:while(true){}",
    "javascript:void(0)",
    "javascript:window.open('http://evil.com')",
    "javascript:fetch('//evil.com')",
    "javascript:confirm('click me')",
    "javascript:top.location='http://evil.com'",
    "javascript:alert(String.fromCharCode(88,83,83))",
    "data:text/html,<script>alert(1)</script>",
    "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    "data:image/svg+xml,<svg onload=alert(1)>",
    "data:text/plain,HelloWorld",
    'data:application/json,{"x":1}',
    "data:text/html,<iframe src=javascript:alert(1)>",
    "data:text/html,<img src=x onerror=alert(2)>",
    "data:application/javascript,alert(1)",
    "data:application/xml,<x><y></y></x>",
    "data:text/html,<a href=javascript:alert(3)>X</a>",
    'vbscript:msgbox("hi")',
    'vbscript:alert("oops")',
    'vbscript:document.write("evil")',
    'vbscript:while 1:wscript.echo "loop":wend',
    'vbscript:CreateObject("Wscript.Shell").Run("calc.exe")',
    "vbscript:call test()",
    'vbscript:execute("msgbox 1")',
    "vbscript:on error resume next",
    'vbscript:window.open("http://bad.com")',
    "vbscript:stop",
    "moz-icon://stock/gtk-home",
    "moz-extension://abc123/page.html",
    "moz-filedata://something",
    "moz-safe-about:config",
    "moz-icon://thunderbird",
    "moz-icon://firefox",
    "moz-filedata://fake",
    "moz-another:test",
    "moz-file://etc/passwd",
    "moz-icon://something.png",
    "about:config",
    "about:blank",
    "about:crash",
    "about:robots",
    "about:memory",
    "about:preferences",
    "about:plugins",
    "about:networking",
    "about:cache",
    "about:logo",
    "resource://gre/res/html.css",
    "resource://gre/res/forms.css",
    "resource://app/chrome/toolkit",
    "resource://test/page.html",
    "resource://example/resource.png",
    "resource://addon/bootstrap.js",
    "resource://pdf.js/build/pdf.js",
    "resource://plugin/plugin.xpi",
    "resource://gre/modules/XPCOMUtils.jsm",
    "resource://system/file",
    "jar:http://evil.com/evil.jar!/test.html",
    "jar:file:///tmp/test.jar!/a.html",
    "jar:https://good.com/app.jar!/index.html",
    "jar:ftp://fileserver/file.jar!/readme.txt",
    "jar:jar:file.zip!/nested.jar!/evil.html",
    "jar:file:///c:/windows/system32/calc.exe!/a.html",
    "jar:http://bad.com/xss.jar!/script.js",
    "jar:file:///etc/passwd!/evil",
    "jar:https://cdn.site/app.jar!/main.js",
    "jar:file:///usr/share/icons.jar!/icon.png",
    "chrome://settings/",
    "chrome://flags/",
    "chrome://downloads/",
    "chrome://extensions/",
    "chrome://version/",
    "chrome://crashes/",
    "chrome://gpu/",
    "chrome://help/",
    "chrome://sandbox/",
    "chrome://sync/",
    "edge://settings/",
    "edge://favorites/",
    "edge://history/",
    "edge://flags/",
    "edge://downloads/",
    "edge://extensions/",
    "edge://gpu/",
    "edge://help/",
    "edge://sandbox/",
    "edge://version/",
    "view-source:http://example.com",
    "view-source:https://google.com",
    "view-source:javascript:alert(1)",
    "view-source:ftp://ftp.example.com",
    "view-source:data:text/html,<b>hi</b>",
    "view-source:about:blank",
    "view-source:file:///etc/passwd",
    "view-source:chrome://settings/",
    "view-source:edge://flags/",
    "view-source:resource://gre/res/html.css",
    # URLs with authentication
    "https://user:password@example.com",
    "https://user:password@example.com",
    "user:password@example.com",
    "https://user:pass@ftp.example.com",
    "user:pass@ftp.example.com",
    "ftp://user:pass@ftp.example.com",
    "ftp://user:pass@ftp.example.com",
)

OTHERWISE_INVALID_URLS = (
    "https://aaa",
    "https://asdfasdfasdf",
    "asdfasdf://asdfasdfasdf",
    "asdfasdf://asdfasdfasdf.asdf",
)

INVALID_URLS_TO_VALIDATE = INVALID_MOCK_URLS_FOR_NORMALIZED + OTHERWISE_INVALID_URLS


@pytest.mark.parametrize(
    "url_to_validate",
    [url_to_validate for url_to_validate in VALID_MOCK_URLS_FOR_VALIDATE],
)
def test_validate_urls(url_to_validate: str):
    url_validator = UrlValidator()
    assert (
        url_validator.validate_url(url_to_validate) == ada_url.URL(url_to_validate).href
    )


@pytest.mark.parametrize(
    "url_to_validate",
    [url_to_validate for url_to_validate in URLS_WITH_DIFFERENT_PATH],
)
def test_validate_urls_with_different_paths(url_to_validate: str):
    url_validator = UrlValidator()
    all_urls_to_test = [
        url_to_validate,
    ] + URLS_WITH_DIFFERENT_PATH[url_to_validate]

    for original_url in all_urls_to_test:
        for url_to_test in all_urls_to_test:
            normalized_url = url_validator.normalize_url(url_to_test)
            validated_url = url_validator.validate_url(normalized_url)

            assert url_to_test == validated_url

            if url_to_test == original_url:
                continue

            assert validated_url != original_url


@pytest.mark.parametrize(
    "url_to_validate", [url_to_validate for url_to_validate in OTHERWISE_INVALID_URLS]
)
def test_validate_invalid_urls(url_to_validate: str):
    url_validator = UrlValidator()
    with pytest.raises(InvalidURLError):
        normalized_url = url_validator.normalize_url(url_to_validate)
        url_validator.validate_url(normalized_url)


@pytest.mark.parametrize(
    "normalized_url,urls_to_validate",
    [
        (
            normalized_url,
            urls_to_validate,
        )
        for normalized_url, urls_to_validate in VALID_MOCK_URLS_FOR_NORMALIZE.items()
    ],
)
def test_normalize_urls_valid(normalized_url: str, urls_to_validate: list[str]):
    url_validator = UrlValidator()
    for url in urls_to_validate:
        assert (
            normalized_url.lower() == url_validator.normalize_url(url).lower()
        ), f"Normalized={normalized_url} | Tested={url}"


@pytest.mark.parametrize(
    "scheme",
    [
        scheme
        for scheme in url_constants.CORE_SCHEMES | url_constants.OTHER_VALID_SCHEMES
    ],
)
def test_normalize_url_schemes(scheme: str):
    url_validator = UrlValidator()
    url_for_test = scheme + ":urls4irl.app"
    assert url_for_test.lower() == url_validator.normalize_url(url_for_test).lower()


@pytest.mark.parametrize("dev_url", [dev_url for dev_url in url_constants.DEV_URLS])
def test_normalize_dev_urls(dev_url: str):
    url_validator = UrlValidator()
    dev_url_with_port = dev_url + ":8080"
    assert "http://" + dev_url_with_port.lower() == url_validator.normalize_url(
        dev_url_with_port
    )
    assert "http://" + dev_url == url_validator.normalize_url(dev_url)


@pytest.mark.parametrize(
    "invalid_url", [invalid_url for invalid_url in INVALID_MOCK_URLS_FOR_NORMALIZED]
)
def test_normalize_urls_invalid(invalid_url: str):
    url_validator = UrlValidator()
    with pytest.raises(InvalidURLError):
        url_validator.normalize_url(invalid_url)
